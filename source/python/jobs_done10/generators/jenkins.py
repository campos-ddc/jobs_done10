'''
Module containing everything related to Jenkins in jobs_done10.

This includes a generator, job publishers, constants and command line interface commands.
'''
from __future__ import absolute_import, with_statement
from ben10.foundation.bunch import Bunch
from ben10.foundation.decorators import Implements
from ben10.interface import ImplementsInterface
from jobs_done10.job_generator import IJobGenerator



#===================================================================================================
# JenkinsJob
#===================================================================================================
class JenkinsJob(Bunch):
    '''
    Represents a Jenkins job.

    :cvar str name:
        Job name

    :cvar str xml:
        Job XML contents
    '''
    name = None
    xml = None



#===================================================================================================
# JenkinsXmlJobGenerator
#===================================================================================================
class JenkinsXmlJobGenerator(object):
    '''
    Generates Jenkins jobs.
    '''
    ImplementsInterface(IJobGenerator)

    @Implements(IJobGenerator.__init__)
    def __init__(self, repository):
        self.repository = repository

        # TODO: Create interface for this attribute
        self.job_group = repository.name + '-' + repository.branch


    @Implements(IJobGenerator.Reset)
    def Reset(self):
        from pyjenkins import JenkinsJobGenerator as PyJenkinsJobGenerator

        self.__jjgen = PyJenkinsJobGenerator(self.repository.name)
        self.__jjgen.branch = self.repository.branch
        self.__jjgen.assigned_node = '%(id)s%(variations)s'
        self.__jjgen.job_name_format = '%(id)s-%(branch)s%(variations)s'

        # Configure description
        self.__jjgen.description = '<!-- Managed by Jenkins Job Builder -->'

        # Configure git SCM
        git_plugin = self.__jjgen.AddPlugin('git', self.repository.url)
        git_plugin.target_dir = self.repository.name
        pass


    @Implements(IJobGenerator.GenerateJobs)
    def GenerateJobs(self):
        return JenkinsJob(
            name=self.__jjgen.GetJobName(),
            xml=self.__jjgen.GetContent(),
        )


    #===============================================================================================
    # Configurator functions (..seealso:: JobsDoneFile ivars for docs)
    #===============================================================================================
    @Implements(IJobGenerator.SetMatrixRow)
    def SetMatrixRow(self, matrix_row):
        if matrix_row:
            self.__jjgen.variations = '-' + '-'.join([i[1] for i in sorted(matrix_row.items())])
        else:
            self.__jjgen.variations = ''


    def SetParameters(self, parameters):
        for i_parameter in parameters:
            for _name, j_dict  in i_parameter.iteritems():
                self.__jjgen.AddChoiceParameter(
                    j_dict['name'],
                    description=j_dict['description'],
                    choices=j_dict['choices'],
                )


    def SetJunitPatterns(self, junit_patterns):
        xunit_plugin = self.__jjgen.AddPlugin("xunit")
        xunit_plugin.junit_patterns = junit_patterns


    def SetBoosttestPatterns(self, boosttest_patterns):
        xunit_plugin = self.__jjgen.AddPlugin("xunit")
        xunit_plugin.boost_patterns = boosttest_patterns


    def SetDescriptionRegex(self, description_regex):
        if description_regex:
            self.__jjgen.AddPlugin("description-setter", description_regex)


    def SetBuildBatchCommands(self, build_batch_commands):
        p = self.__jjgen.AddPlugin("batch")
        p.command_lines += build_batch_commands


    def SetBuildShellCommands(self, build_shell_commands):
        p = self.__jjgen.AddPlugin("shell")
        p.command_lines += build_shell_commands



#===================================================================================================
# JenkinsJobPublisher
#===================================================================================================
class JenkinsJobPublisher(object):
    '''
    Publishes `JenkinsJob`s
    '''
    def __init__(self, job_group, jobs):
        '''

        :param str job_group:
            Group to which these jobs belong to.

            This is used find and delete/update jobs that belong to the same group during upload.

        :param list(JenkinsJob) jobs:
            List of jobs to be published. They must all belong to the same `job_group` (name must
            start with `job_group`)
        '''
        self.job_group = job_group
        self.jobs = dict((job.name, job) for job in jobs)

        for job_name in self.jobs.keys():
            assert job_name.startswith(job_group)


    def PublishToUrl(self, url, username=None, password=None):
        '''
        Publishes new jobs, updated existing jobs, and delete jobs that belong to the same
        `self.job_group` but were not updated.

        :param str url:
            Jenkins instance URL where jobs will be uploaded to.

        :param str username:
            Jenkins username.

        :param str password:
            Jenkins password.

        :return tuple(list(str),list(str),list(str)):
            Tuple with lists of {new, updated, deleted} job names (sorted alphabetically)
        '''
        # Push to url using jenkins_api
        import jenkins
        jenkins = jenkins.Jenkins(url, username, password)

        job_names = set(self.jobs.keys())

        all_jobs = set([str(job['name']) for job in jenkins.get_jobs()])
        matching_jobs = set([job for job in all_jobs if job.startswith(self.job_group)])

        new_jobs = job_names.difference(matching_jobs)
        updated_jobs = job_names.intersection(matching_jobs)
        deleted_jobs = matching_jobs.difference(job_names)

        for job_name in new_jobs:
            jenkins.create_job(job_name, self.jobs[job_name].xml)

        for job_name in updated_jobs:
            jenkins.reconfig_job(job_name, self.jobs[job_name].xml)

        for job_name in deleted_jobs:
            jenkins.delete_job(job_name)

        return map(sorted, (new_jobs, updated_jobs, deleted_jobs))


    def PublishToDirectory(self, output_directory):
        '''
        Publishes jobs to a directory. Each job creates a file with its name and xml contents.

        :param str output_directory:
             Target directory for outputting job .xmls
        '''
        from ben10.filesystem import CreateFile
        import os
        for job in self.jobs.values():
            CreateFile(
                filename=os.path.join(output_directory, job.name),
                contents=job.xml
            )



#===================================================================================================
# Actions for common uses of Jenkins classes
#===================================================================================================
def UploadJobsFromFile(repository, jobs_done_file_contents, url, username=None, password=None):
    '''
    :param repository:
        ..seealso:: GetJobsFromFile

    :param jobs_done_file_contents:
        ..seealso:: GetJobsFromFile

    :param str url:
        URL of a Jenkins sevrer instance where jobs will be uploaded

    :param str|None username:
        Username for Jenkins server.

    :param str|None password:
        Password for Jenkins server.

    :returns:
        ..seealso:: JenkinsJobPublisher.PublishToUrl

    '''
    job_group, jobs = GetJobsFromFile(repository, jobs_done_file_contents)
    publisher = JenkinsJobPublisher(job_group, jobs)

    return publisher.PublishToUrl(url, username, password)



def GetJobsFromDirectory(directory='.'):
    '''
    Looks in a directory for a jobs_done file and git repository information to create jobs.

    :param directory:
        Directory where we'll extract information to generate `JenkinsJob`s

    :return set(JenkinsJob)
    '''
    from ben10.filesystem import FileNotFoundError, GetFileContents
    from jobs_done10.git import Git
    from jobs_done10.jobs_done_file import JOBS_DONE_FILENAME
    from jobs_done10.repository import Repository
    import os

    git = Git()
    repository = Repository(
        url=git.GetRemoteUrl(repo_path=directory),
        branch=git.GetCurrentBranch(repo_path=directory)
    )

    try:
        jobs_done_file_contents = GetFileContents(os.path.join(directory, JOBS_DONE_FILENAME))
    except FileNotFoundError:
        jobs_done_file_contents = None

    return GetJobsFromFile(repository, jobs_done_file_contents)



def GetJobsFromFile(repository, jobs_done_file_contents):
    '''
    Creates jobs from repository information and a jobs_done file.

    :param Repository repository:
        ..seealso:: Repository

    :param str|None jobs_done_file_contents:
        ..seealso:: JobsDoneFile.CreateFromYAML

    :return set(JenkinsJob)
    '''
    from jobs_done10.job_generator import JobGeneratorConfigurator
    from jobs_done10.jobs_done_file import JobsDoneFile
    import re

    jenkins_generator = JenkinsXmlJobGenerator(repository)

    jobs = []
    jobs_done_files = JobsDoneFile.CreateFromYAML(jobs_done_file_contents)
    for jobs_done_file in jobs_done_files:
        # If jobs_done file defines patterns for acceptable branches to create jobs, compare those
        # against the current branch, to determine if we should generate jobs or not.
        if jobs_done_file.branch_patterns is not None:
            if not any([re.match(pattern, repository.branch) for pattern in jobs_done_file.branch_patterns]):
                continue

        JobGeneratorConfigurator.Configure(jenkins_generator, jobs_done_file)
        jobs.append(jenkins_generator.GenerateJobs())

    return jenkins_generator.job_group, jobs



#===================================================================================================
# ConfigureCommandLineInterface
#===================================================================================================
def ConfigureCommandLineInterface(jobs_done_application):
    '''
    Configures additional command line commands to the jobs_done application.

    :param App jobs_done_application:
        Command line application we are registering commands to.
    '''

    @jobs_done_application
    def jenkins(console_, url, username=None, password=None):
        '''
        Creates jobs for Jenkins and push them to a Jenkins instance.

        If no parameters are given, this command will look for a configuration file that defines a
        target url/username/password.

        :param url: Jenkins instance URL where jobs will be uploaded to.

        :param username: Jenkins username.

        :param password: Jenkins password.
        '''
        directory = '.'

        job_group, jobs = GetJobsFromDirectory(directory)

        console_.Print('Publishing jobs in "<white>%s</>"' % url)

        new_jobs, updated_jobs, deleted_jobs = JenkinsJobPublisher(job_group, jobs).PublishToUrl(
            url, username, password)

        for job in new_jobs:
            console_.Print('<green>NEW</> - ' + job)
        for job in updated_jobs:
            console_.Print('<yellow>UPD</> - ' + job)
        for job in deleted_jobs:
            console_.Print('<red>DEL</> - ' + job)


    @jobs_done_application
    def jenkins_test(console_, output_directory):
        '''
        Creates jobs for Jenkins and save the resulting .xml's in a directory

        :param output_directory: Directory to output job xmls instead of uploading to `url`.
        '''
        directory = '.'
        jobs = GetJobsFromDirectory(directory)

        console_.Print('Saving jobs in "%s"' % output_directory)
        JenkinsJobPublisher(jobs).PublishToDirectory(output_directory)
        console_.ProgressOk()