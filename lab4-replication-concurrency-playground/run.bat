@echo off
echo ============================================================
echo Key-Value Store with Single-Leader Replication
echo ============================================================

if "%1"=="build" goto build
if "%1"=="start" goto start
if "%1"=="stop" goto stop
if "%1"=="restart" goto restart
if "%1"=="logs" goto logs
if "%1"=="test" goto test
if "%1"=="performance" goto performance
if "%1"=="clean" goto clean
if "%1"=="status" goto status
goto help

:build
echo Building Docker images...
docker-compose build
goto end

:start
echo Starting all services...
docker-compose up -d
echo.
echo Waiting for services to start...
timeout /t 10 /nobreak > nul
echo.
echo Services started! Access points:
echo   Leader:     http://localhost:8000
echo   Follower 1: http://localhost:8001
echo   Follower 2: http://localhost:8002
echo   Follower 3: http://localhost:8003
echo   Follower 4: http://localhost:8004
echo   Follower 5: http://localhost:8005
echo.
echo Use "run.bat logs" to see the logs
goto end

:stop
echo Stopping all services...
docker-compose down
goto end

:restart
echo Restarting all services...
docker-compose restart
goto end

:logs
echo Showing logs (press Ctrl+C to exit)...
docker-compose logs -f
goto end

:test
echo Running integration tests...
pip install -r requirements.txt -q
pytest test_integration.py -v
goto end

:performance
echo Running performance analysis...
pip install -r requirements.txt -q
python performance_analysis.py
goto end

:clean
echo Cleaning up containers and images...
docker-compose down --rmi all -v
goto end

:status
echo Container status:
docker-compose ps
goto end

:help
echo Usage: run.bat [command]
echo.
echo Commands:
echo   build       Build Docker images
echo   start       Start all services (leader + 5 followers)
echo   stop        Stop all services
echo   restart     Restart all services
echo   logs        Show logs from all services
echo   test        Run integration tests
echo   performance Run performance analysis
echo   clean       Remove all containers and images
echo   status      Show container status
echo.
echo Example:
echo   run.bat build
echo   run.bat start
echo   run.bat test
goto end

:end
