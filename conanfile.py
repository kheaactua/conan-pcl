from __future__ import print_function
from conans import ConanFile, CMake
import re


class PclConan(ConanFile):
    name = "pcl"
    version = "1.8.1"
    license = "BSD"
    url = "http://docs.pointclouds.org/"
    description = "Point cloud library"
    settings = "os", "compiler", "build_type", "arch"
    build_policy="missing"
    generators = "cmake"
    requires = (
        'boost/1.66.0@conan/stable',
        'eigen/3.3.4@3dri/stable',
        'flann/1.9.1@3dri/stable',
        'qhull/2015.2@3dri/stable',
        'vtk/7.1.1@jmdaly/testing', # TODO Change!
        'Qt/5.9.3@3dri/stable',
    )
    options = {
        'shared': [True, False],
    }
    default_options = ("shared=True")

    def source(self):
        self.run(f'git clone https://github.com/PointCloudLibrary/pcl.git {self.name}')
        self.run(f'cd {self.name} && git checkout pcl-{self.version}')

    def configure(self):
        self.options["boost"].shared = self.options.shared

    def build(self):

        pcl_major = '.'.join(self.version.split('.')[:2])
        vtk_major = '.'.join(self.deps_cpp_info['vtk'].version.split('.')[:2])

        # TODO See if we can use self.deps_cpp_info['vtk'].res
        vtk_cmake_rel_dir = f'lib/cmake/vtk-{vtk_major}'
        vtk_cmake_dir = f'{self.deps_cpp_info["vtk"].rootpath}/{vtk_cmake_rel_dir}'

        args = []
        if self.options.shared:

        args.append('-DCMAKE_CXX_FLAGS=-mtune=generic"')
        args.append('-DBOOST_ROOT:PATH=%s"'%self.deps_cpp_info['boost'].rootpath)
        args.append('-DCMAKE_INSTALL_PREFIX=%s"'%self.package_folder)
        args.append('-DEIGEN3_DIR:PATH=%s/share/eigen3/cmake"'%self.deps_cpp_info['eigen'].rootpath)
        args.append('-DEIGEN_INCLUDE_DIR:PATH=%s/include/eigen3"'%self.deps_cpp_info['eigen'].rootpath)
        args.append('-DFLANN_INCLUDE_DIR:PATH=%s/include"'%self.deps_cpp_info['flann'].rootpath)
        args.append('-DFLANN_LIBRARY:FILEPATH=%s/lib/libflann_cpp.so"'%self.deps_cpp_info['flann'].rootpath)
        args.append('-DQHULL_INCLUDE_DIR:PATH=%s/include"'%self.deps_cpp_info['qhull'].rootpath)
        args.append('-DQHULL_LIBRARY:FILEPATH=%s/lib/libqhull.so"'%self.deps_cpp_info['qhull'].rootpath)
        args.append('-DQt5Core_DIR=%s/lib/cmake/Qt5Core"'%self.deps_cpp_info['Qt'].rootpath)
        args.append('-DQt5_DIR=%s/lib/cmake/Qt5"'%self.deps_cpp_info['Qt'].rootpath)
        args.append('-DQt5Gui_DIR=%s/lib/cmake/Qt5Gui"'%self.deps_cpp_info['Qt'].rootpath)
        args.append('-DQt5OpenGL_DIR=%s/lib/cmake/Qt5OpenGL"'%self.deps_cpp_info['Qt'].rootpath)
        args.append('-DQt5Widgets_DIR=%s/lib/cmake/Qt5Widgets"'%self.deps_cpp_info['Qt'].rootpath)
        args.append(f'-DVTK_DIR={vtk_cmake_dir}"')
        args.append('-DBUILD_surface_on_nurbs=ON')

        cmake = CMake(self)
        build_folder = f'{self.source_folder}/{self.name}'
        # Not using cmake.configure() because it escapes the arguments in a way
        # that CMake doesn't like them.
        # self.run(f'cd {build_folder} && cmake . {cmake.command_line} %s'%' '.join(args))
        cmake.configure(source_path=self.name, args=args)
        cmake.build(build_dir=f'{build_folder}')
        cmake.install(build_dir=f'{build_folder}')

        # Fix up the CMake Find Script PCL generated
        self.output.info('Inserting Conan variables in to the PCL CMake Find script.')
        fixFindPackage(os.path.join(build_folder, cmakeRelDir()), pcl_major, vtk_cmake_rel_dir)

    def fixFindPackage(self, cmake_path, pcl_major, vtk_cmake_rel_dir):
        """
        Insert some variables into the PCL find script generated in the
        build so that we can use it in our CMake scripts
        """

        # Now, run some regex's through the
        with open(f'{cmake_path}/PCLConfig.cmake') as f:
            data = f.read()

        sub_map = {
            'eigen': os.path.join('${CONAN_INCLUDE_DIRS_EIGEN}', 'eigen3'),
            'boost': '${CONAN_INCLUDE_DIRS_BOOST}',
            'flann': '${CONAN_INCLUDE_DIRS_FLANN}',
            'qhull': '${CONAN_INCLUDE_DIRS_QHULL}',
            'vtk':   os.path.join('${CONAN_VTK_ROOT}', vtk_cmake_rel_dir),
            'pcl':   os.path.join('${CONAN_PCL_ROOT}', 'pcl')
        }

        # https://regex101.com/r/fZxj7i/1
        regex = r"(?<=\").*?conan.*?(?P<package>(%s)).*?(?=\")"

        for pkg, rep in sub_map.items():
            r = regex%pkg
            m = re.search(r, data)
            if m:
                data = data[0:m.start()] + rep + data[m.end():]
            else:
                self.output.warning('Could not find %s'%pkg)


    def cmakeRelDir():
        """ Grab the directory PCL's cmake is in """
        pcl_major = '.'.join(self.version.split('.')[:2])
        return os.path.join('share', f'pcl-{pcl_major}')

    def package(self):
        pass

    def package_info(self):
        # PCL should be loaded with a Find script written by PCL, so no need
        # for us to know which specific libs and such need to be included.
        # (Well, this assumption will change if a future conan file that
        # depends on PCL for some reason needs to be able to check out its libs
        # and stuff)

        # Add the directory with CMake.. Not sure if this is a good use of resdirs
        self.cpp_info.resdirs = [cmakeRelDir()]
