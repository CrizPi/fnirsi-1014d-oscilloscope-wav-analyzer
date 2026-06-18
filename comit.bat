@echo off
git add -A
if "%1"=="" (
    git commit -m "update"
) else (
    git commit -m "%*"
)
git status
