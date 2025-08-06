@echo off
chcp 65001 >nul
setlocal

REM ✅ 1. Activate virtual environment
call .\.venv\libra_env\Scripts\activate.bat

REM ✅ 2. Set PYTHONPATH
set PYTHONPATH=%~dp0services

REM ✅ 3. Data Setting
echo [STEP 1] Data Setting
set EXECUTION_SEQUENCE=[{"package": "DataHandling"},{"package": "DBHandling"}]
cd /d .\services\data_service
python __main__.py
cd /d %~dp0

REM ✅ 4. Run model creation for Model 01
echo [STEP 1] Creating Model 01
set EXECUTION_SEQUENCE=[{"package":"ModelCreator","config":"Num01_Config_XGB.json"}]
cd /d .\services\ml_service
python __main__.py
cd /d %~dp0

REM ✅ 5. Run prediction for Model 01
echo [STEP 2] Predicting with Model 01
set EXECUTION_SEQUENCE=[{"package":"Predictor","config":"Num01_Config_XGB.json"}]
cd /d .\services\prediction_service
python __main__.py
cd /d %~dp0

REM ✅ 6. Run model creation for Model 02
echo [STEP 3] Creating Model 02
set EXECUTION_SEQUENCE=[{"package":"ModelCreator","config":"Num02_Config_XGB.json"}]
cd /d .\services\ml_service
python __main__.py
cd /d %~dp0

REM ✅ 7. Run prediction for Model 02
echo [STEP 4] Predicting with Model 02
set EXECUTION_SEQUENCE=[{"package":"Predictor","config":"Num02_Config_XGB.json"}]
cd /d .\services\prediction_service
python __main__.py
cd /d %~dp0

echo.
echo ✅ Pipeline completed successfully!
endlocal
pause
