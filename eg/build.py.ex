import mirbuild
project = mirbuild.CMakeProject('libcommons-core')
project.depends('libmoost')

#### 1) default :)

#### 2) glob
# project.test('test/*')

#### 3) explicit directories ("test" executable is implicit)
# project.test('test/algo', 'test/containers', 'test/io')

#### 4) explicit naming of test executables
# project.test(['test/algo', 'test'], ['test/containers', 'test'], ['test/io', 'test'])

#### 5) in case the executables are built by the main CMakeLists.txt
# project.test([None, 'test/algo/test', 'test/containers/test', 'test/io/test'])

#### 6) using TestBuilder and Test objects
# project.test(mirbuild.CMakeTestBuilder(project.env, 'test/algo', 'test'),
#              mirbuild.CMakeTestBuilder(project.env, 'test/containers', ['cont-test', 'test']),
#              mirbuild.CMakeTestBuilder(project.env, 'test/io', mirbuild.Test('io-test', 'test')))

#### 7) using an explicit runner (works for all of the above)
# project.test('test/*', runner = mirbuild.BoostTestRunner)

project.run()
