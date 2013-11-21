from aasimar10.shared_commands import BuildCommand
from coilib50.basic.override import Override



#===================================================================================================
# JobsDone10BuildCommand
#===================================================================================================
class JobsDone10BuildCommand(BuildCommand):

    name = 'JobsDone10BuildCommand'

    @Override(BuildCommand.EvBuild)
    def EvBuild(self, args):
        self.Clean()
        self.RunTests(jobs=8, xml=True, verbose=1)