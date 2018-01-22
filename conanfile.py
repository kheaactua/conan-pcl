from __future__ import print_function
from conans import ConanFile, CMake


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
        'vtk/7.1.1@jmdaly/testing',
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

        vtk_major = '.'.join(self.deps_cpp_info['vtk'].version.split('.')[:2])

        args = []
        if self.options.shared:
            args.append("-DBUILD_SHARED_LIBS=ON")
        args.append('-DCMAKE_CXX_FLAGS="-mtune=generic"')
        args.append('-DBOOST_ROOT:PATH="%s"'%self.deps_cpp_info["boost"].rootpath)
        args.append('-DCMAKE_INSTALL_PREFIX="%s"'%self.package_folder)
        args.append('-DEIGEN3_DIR:PATH="%s/share/eigen3/cmake"'%self.deps_cpp_info["eigen"].rootpath)
        args.append('-DEIGEN_INCLUDE_DIR:PATH="%s/include/eigen3"'%self.deps_cpp_info["eigen"].rootpath)
        args.append('-DFLANN_INCLUDE_DIR:PATH="%s/include"'%self.deps_cpp_info["flann"].rootpath)
        args.append('-DFLANN_LIBRARY:FILEPATH="%s/lib/libflann_cpp.so"'%self.deps_cpp_info["flann"].rootpath)
        args.append('-DQHULL_INCLUDE_DIR:PATH="%s/include"'%self.deps_cpp_info["qhull"].rootpath)
        args.append('-DQHULL_LIBRARY:FILEPATH="%s/lib/libqhull.so"'%self.deps_cpp_info["qhull"].rootpath)
        args.append('-DQt5Core_DIR="%s/lib/cmake/Qt5Core"'%self.deps_cpp_info["Qt"].rootpath)
        args.append('-DQt5_DIR="%s/lib/cmake/Qt5"'%self.deps_cpp_info["Qt"].rootpath)
        args.append('-DQt5Gui_DIR="%s/lib/cmake/Qt5Gui"'%self.deps_cpp_info["Qt"].rootpath)
        args.append('-DQt5OpenGL_DIR="%s/lib/cmake/Qt5OpenGL"'%self.deps_cpp_info["Qt"].rootpath)
        args.append('-DQt5Widgets_DIR="%s/lib/cmake/Qt5Widgets"'%self.deps_cpp_info["Qt"].rootpath)
        args.append(f'-DVTK_DIR="%s/lib/cmake/vtk-{vtk_major}"'%self.deps_cpp_info["vtk"].rootpath)
        args.append('-DBUILD_surface_on_nurbs=ON')

        cmake = CMake(self)
        build_folder = f'{self.source_folder}/{self.name}'
        # Not using cmake.configure() because it escapes the arguments in a way
        # that CMake doesn't like them.
        self.run(f'cd {build_folder} && cmake . {cmake.command_line} %s'%' '.join(args))
        cmake.build(build_dir=f'{build_folder}')
        cmake.install(build_dir=f'{build_folder}')

    def package(self):
        pass

    def package_info(self):
        self.cpp_info.libs = []
