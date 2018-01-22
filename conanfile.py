from __future__ import print_function
from conans import ConanFile, CMake


class PclConan(ConanFile):
    name = "pcl"
    version = "1.8.0"
    license = "BSD"
    url = "http://docs.pointclouds.org/"
    description = "Point cloud library"
    settings = "os", "compiler", "build_type", "arch"
    generators = "cmake"
    requires = (
        'boost/1.66.0@conan/stable',
        'eigen/3.3.4@3dri/stable',
        'flann/1.9.1@3dri/stable',
        'qhull/2015.2@3dri/stable',
        'vtk/7.1.1@jmdaly/testing',
        'Qt/5.9.3@3dri/stable',
    )

    def source(self):
        self.run("git clone https://github.com/PointCloudLibrary/pcl.git")
        self.run("cd pcl && git checkout pcl-%s"%self.version)

    def build(self):


        args = []
        args.append("-DBUILD_SHARED_LIBS=ON")
        args.append('-DCMAKE_CXX_FLAGS="-std=c++11 -DBOOST_MATH_DISABLE_FLOAT128"')
        args.append('-DCMAKE_INSTALL_PREFIX="%s"' % self.package_folder)
        args.append('-DEIGEN_INCLUDE_DIR:PATH="%s"/include/eigen3' % self.deps_cpp_info["eigen"].rootpath)
        args.append('-DFLANN_INCLUDE_DIR:PATH="%s"/include' % self.deps_cpp_info["flann"].rootpath)
        args.append('-DFLANN_LIBRARY:FILEPATH="%s"/lib/libflann_cpp.so' % self.deps_cpp_info["flann"].rootpath)
        args.append('-DQHULL_INCLUDE_DIR:PATH="%s"/include' % self.deps_cpp_info["qhull"].rootpath)
        args.append('-DQHULL_LIBRARY:FILEPATH="%s"/lib/libqhull.so' % self.deps_cpp_info["qhull"].rootpath)
        args.append('-DBOOST_ROOT:PATH="%s"' % self.deps_cpp_info["boost"].rootpath)
        args.append('-DQt5Core_DIR=%s/lib/cmake/Qt5Core' % self.deps_cpp_info["Qt"].rootpath)
        args.append('-DQt5_DIR=%s/lib/cmake/Qt5' % self.deps_cpp_info["Qt"].rootpath)
        args.append('-DQt5Gui_DIR=%s/lib/cmake/Qt5Gui' % self.deps_cpp_info["Qt"].rootpath)
        args.append('-DQt5OpenGL_DIR=%s/lib/cmake/Qt5OpenGL' % self.deps_cpp_info["Qt"].rootpath)
        args.append('-DQt5Widgets_DIR=%s/lib/cmake/Qt5Widgets' % self.deps_cpp_info["Qt"].rootpath)
        args.append('-DVTK_DIR=%s/lib/cmake/vtk-7.1' % self.deps_cpp_info["vtk"].rootpath)
        args.append("BUILD_surface_on_nurbs='ON'")

        cmake = CMake(self)
        cmake.configure(
            source_folder="pcl",
            args=args,
        )
        cmake.build()

        # Explicit way:
        # self.run('cmake %s/hello %s' % (self.source_folder, cmake.command_line))
        # self.run("cmake --build . %s" % cmake.build_config)

    def package(self):
        pass

    def package_info(self):
        self.cpp_info.libs = []
