============================================================================= test session starts ==============================================================================  
platform win32 -- Python 3.13.14, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\mingyu\Desktop\ai_orch\venv1\Scripts\python.exe  
cachedir: .pytest_cache  
rootdir: C:\Users\mingyu\Desktop\ai_orch\week09  
collected 6 items            
test_detect_anomaly.py::test_normal_within_range PASSED                                                    [ 16%]  
test_detect_anomaly.py::test_normal_surge PASSED                                                           [ 33%]  
test_detect_anomaly.py::test_boundary_24_months_is_insufficient PASSED                                     [ 50%]  
test_detect_anomaly.py::test_boundary_zero_std_is_insufficient PASSED                                      [ 66%]  
test_detect_anomaly.py::test_exception_invalid_target_ym PASSED                                            [ 83%]  
test_detect_anomaly.py::test_exception_zero_total_twelve_months_before PASSED                              [100%]  
============================================================================== 6 passed in 0.92s ===============================================================================  