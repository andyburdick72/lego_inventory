# Git Workflow Cheat Sheet

## 1. Create a New Branch
```sh
git checkout main
git pull origin main
git checkout -b your-feature-branch
```
**VS Code Equivalent**  
Open the Source Control panel, click the branch icon, then select "Create new branch from..." and choose `main`.

## 1b. Move GitHub Issue to In Progress
```sh
gh issue develop ISSUE_NUMBER --move "In Progress"
```
**GitHub UI Equivalent**  
Open the issue in GitHub, and from the project board sidebar, move it to the **In Progress** column.

## 2. Activate Virtual Environment
```sh
source .venv/bin/activate
```
**VS Code Equivalent**  s
If VS Code is configured with your `.venv`, it should auto-activate in the integrated terminal. If not, open the Command Palette (⇧⌘P), run `Python: Select Interpreter`, and choose the `.venv` interpreter.

## 3. Make Changes and Commit
```sh
# Stage changes
git add .
# or add specific files:
# git add path/to/file.py

# Commit with a descriptive message
git commit -m "Describe your changes"
```
**VS Code Equivalent**  
In the Source Control panel, stage changes by clicking the `+` button next to files, enter your commit message in the message box, and click the checkmark to commit.

## 4. Merge the Branch
```sh
# Switch to main
git checkout main
# Pull latest changes
git pull origin main
# Merge your branch into main
git merge --no-ff your-feature-branch
```
**VS Code Equivalent**  
Switch to `main` in the Branch menu (bottom-left), pull latest changes from origin, then run `Git: Merge Branch…` from the Command Palette (⇧⌘P) and select your feature branch.

## 5. Delete Your Local Branch (Optional)
```sh
# Switch to main
git checkout main
# Pull latest changes
git pull origin main
# Delete your branch locally
git branch -d your-feature-branch
```
**VS Code Equivalent**  
Use the Branch menu in the bottom-left corner of VS Code to switch to `main`, then select your feature branch name and choose "Delete Branch…".

## 5b. Delete the Remote Branch (Optional)
```sh
git push origin --delete your-feature-branch
```
**VS Code Equivalent**  
Open the Command Palette (⇧⌘P), run `Git: Delete Branch...`, and select the remote branch you want to delete.

## 6. Move GitHub Issue to Done
```sh
gh issue develop ISSUE_NUMBER --move "Done"
```
**GitHub UI Equivalent**  
Open the issue in GitHub, and from the project board sidebar, move it to the **Done** column.

## Notes
- Always pull the latest `main` before creating a new branch.
- Write clear commit messages.
- Use branches for features, fixes, or experiments.
