Option Explicit
Dim shellApp, files, root, launcher
Set shellApp = CreateObject("Shell.Application")
Set files = CreateObject("Scripting.FileSystemObject")
root = files.GetParentFolderName(WScript.ScriptFullName)
launcher = files.BuildPath(root, "INICIAR_JARVIS_AUTOATUALIZAVEL.bat")
shellApp.ShellExecute launcher, "", root, "open", 1
