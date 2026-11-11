@echo off
setlocal
set ROOT=%~dp0..\..
if /I "%1"=="logs" goto logs
pushd "%ROOT%\worker"
docker compose exec -T api python -m app.diagnostics.cli %*
set EXITCODE=%ERRORLEVEL%
popd
exit /b %EXITCODE%

:logs
set RUN_ID=%2
if "%RUN_ID%"=="" (
  echo Usage: tools\diagnostics\diag.cmd logs RUN_ID [--errors]
  exit /b 2
)
pushd "%ROOT%\worker"
if /I "%3"=="--errors" goto logs_errors
if /I "%3"=="--stage" goto logs_stage
docker compose logs --no-color api | findstr /C:"pipeline_run_id=%RUN_ID%" /C:"run_id=%RUN_ID%"
set EXITCODE=%ERRORLEVEL%
popd
exit /b %EXITCODE%

:logs_errors
docker compose logs --no-color api | findstr /C:"pipeline_run_id=%RUN_ID%" /C:"run_id=%RUN_ID%" | findstr /I "failed error"
set EXITCODE=%ERRORLEVEL%
popd
exit /b %EXITCODE%

:logs_stage
docker compose logs --no-color api | findstr /C:"pipeline_run_id=%RUN_ID%" /C:"run_id=%RUN_ID%" | findstr /I "%4"
set EXITCODE=%ERRORLEVEL%
popd
exit /b %EXITCODE%
