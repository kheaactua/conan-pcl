diff --git a/cmake/Modules/FindFLANN.cmake b/cmake/Modules/FindFLANN.cmake
index 964d773..638cc85 100644
--- a/cmake/Modules/FindFLANN.cmake
+++ b/cmake/Modules/FindFLANN.cmake
@@ -55,6 +55,12 @@ if(NOT FLANN_FOUND)
     mark_as_advanced(FLANN_LIBRARY FLANN_LIBRARY_DEBUG FLANN_INCLUDE_DIR)
 endif()
 
+# Add flann_s for lz4 symbols
+find_library(FLANN_S_LIBRARY
+	 NAMES flann_s
+	 PATHS ${FLANN_LIBRARY_DIRS})
+list(APPEND FLANN_LIBRARIES ${FLANN_S_LIBRARY})
+
 if(FLANN_FOUND)
   message(STATUS "FLANN found (include: ${FLANN_INCLUDE_DIRS}, lib: ${FLANN_LIBRARIES})")
   if(FLANN_USE_STATIC)
