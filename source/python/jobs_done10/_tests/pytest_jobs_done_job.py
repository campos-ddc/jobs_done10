from ben10.foundation.string import Dedent
from jobs_done10.jobs_done_job import JobsDoneJob, UnknownJobsDoneFileOption, JobsDoneFileTypeError
import pytest
from jobs_done10.repository import Repository
from ben10.filesystem import CreateFile



#===================================================================================================
# Test
#===================================================================================================
class Test(object):

    _REPOSITORY = Repository(url='https://space.git', branch='milky_way')

    def testCreateJobsDoneJobFromYAML(self):
        ci_contents = Dedent(
            '''
            junit_patterns:
            - "junit*.xml"

            boosttest_patterns:
            - "cpptest*.xml"

            parameters:
            - choice:
                name: "PARAM"
                choices:
                - "choice_1"
                - "choice_2"
                description: "Description"

            build_batch_commands:
            - "command on planet {planet} (repository '{name}' on '{branch}')"

            matrix:
              planet:
              - mercury
              - venus

              moon:
              - europa
            '''
        )
        jobs_done_jobs = JobsDoneJob.CreateFromYAML(ci_contents, repository=self._REPOSITORY)

        # Two possible variations (mercury-europa and venus-europa)
        assert len(jobs_done_jobs) == 2

        def CheckCommonValues(jobs_done_job):
            assert jobs_done_job.matrix == {'moon': ['europa'], 'planet': ['mercury', 'venus']}
            assert jobs_done_job.junit_patterns == ['junit*.xml']
            assert jobs_done_job.boosttest_patterns == ['cpptest*.xml']
            assert jobs_done_job.parameters == [{
                'choice' : {
                    'name': 'PARAM',
                    'choices': ['choice_1', 'choice_2'],
                    'description': 'Description',
                }
            }]

        CheckCommonValues(jobs_done_jobs[0])
        CheckCommonValues(jobs_done_jobs[1])

        # Tests for specific jobs
        mercury_job = jobs_done_jobs[0] if jobs_done_jobs[0].matrix_row['planet'] == 'mercury' else jobs_done_jobs[1]
        venus_job = jobs_done_jobs[0] if jobs_done_jobs[0].matrix_row['planet'] == 'venus' else jobs_done_jobs[1]

        assert mercury_job.matrix_row == {'moon': 'europa', 'planet': 'mercury'}
        assert venus_job.matrix_row == {'moon': 'europa', 'planet': 'venus'}

        # In this case, our commands use some replacement variables, including variables defined in
        # 'matrix', and special cases 'name' and 'branch' based on repository.
        assert mercury_job.build_batch_commands == [
            "command on planet mercury (repository 'space' on 'milky_way')"]
        assert venus_job.build_batch_commands == [
            "command on planet venus (repository 'space' on 'milky_way')"]


    def testCreateJobsDoneJobFromYAMLWithConditions(self):
        ci_contents = Dedent(
            '''
            platform-windows:junit_patterns:
            - "junit*.xml"

            platform-linux:build_shell_commands:
            - "{platform} command"

            platform-windows:build_batch_commands:
            - "{platform} command"

            matrix:
                platform:
                - linux
                - windows
            '''
        )
        for jd_file in JobsDoneJob.CreateFromYAML(ci_contents, repository=self._REPOSITORY):
            if jd_file.matrix_row['platform'] == 'linux':
                assert jd_file.junit_patterns == None
                assert jd_file.build_batch_commands == None
                assert jd_file.build_shell_commands == ['linux command']
            else:
                assert jd_file.junit_patterns == ['junit*.xml']
                assert jd_file.build_batch_commands == ['windows command']
                assert jd_file.build_shell_commands == None


    def testBranchPatterns(self, embed_data):
        base_contents = Dedent(
            '''
            matrix:
                planet:
                - mars
                - earth
                - venus

            '''
        )
        # Using a pattern that does not match our branch will prevent jobs from being generated
        jd_file_contents = base_contents + Dedent(
            '''
            branch_patterns:
            - feature-.*
            '''
        )
        jobs = JobsDoneJob.CreateFromYAML(jd_file_contents, repository=self._REPOSITORY)
        assert len(jobs) == 0

        # Matching patterns work as usual
        jd_file_contents = base_contents + Dedent(
            '''
            branch_patterns:
            - milky_way
            '''
        )
        jobs = JobsDoneJob.CreateFromYAML(jd_file_contents, repository=self._REPOSITORY)
        assert len(jobs) == 3

        # Also works with several patterns and regexes
        jd_file_contents = base_contents + Dedent(
            '''
            branch_patterns:
            - master
            - milky.*
            '''
        )
        jobs = JobsDoneJob.CreateFromYAML(jd_file_contents, repository=self._REPOSITORY)
        assert len(jobs) == 3


    def testUnknownOption(self):
        # Unknown options should fail
        ci_contents = Dedent(
            '''
            bad_option: value
            '''
        )
        with pytest.raises(UnknownJobsDoneFileOption) as e:
            JobsDoneJob.CreateFromYAML(ci_contents, repository=self._REPOSITORY)

        assert e.value.option_name == 'bad_option'


    def testTypeChecking(self):
        # List is the correct type for build_batch_commands
        ci_contents = Dedent(
            '''
            build_batch_commands:
            - "list item 1"
            '''
        )
        JobsDoneJob.CreateFromYAML(ci_contents, repository=self._REPOSITORY)

        # Trying to set a different value, should raise an error
        ci_contents = Dedent(
            '''
            build_batch_commands: "string item"
            '''
        )
        with pytest.raises(JobsDoneFileTypeError) as e:
            JobsDoneJob.CreateFromYAML(ci_contents, repository=self._REPOSITORY)

        assert e.value.option_name == 'build_batch_commands'
        assert e.value.expected_type == JobsDoneJob.PARSEABLE_OPTIONS['build_batch_commands']
        assert e.value.obtained_type == str


    def testCreateFomrFile(self, embed_data):
        contents = Dedent(
            '''
            matrix:
                planet:
                - mars
                - earth
                - venus

            '''
        )
        filename = embed_data['.jobs_done.yaml']
        CreateFile(filename, contents)

        jobs = JobsDoneJob.CreateFromFile(filename, repository=self._REPOSITORY)

        assert len(jobs) == 3


    def testStringConversion(self):
        '''
        Asserts that our YAML parser converts all basic values to strings (non unicode)
        '''
        contents = Dedent(
            '''
            junit_patterns:
                - 1
            '''
        )
        jobs = JobsDoneJob.CreateFromYAML(contents, repository=self._REPOSITORY)

        assert jobs[0].junit_patterns != [1]
        assert jobs[0].junit_patterns == ['1']