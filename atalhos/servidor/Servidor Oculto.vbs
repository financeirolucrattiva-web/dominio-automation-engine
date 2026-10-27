' Abre o loop do servidor sem janela de console. Usado pela tarefa agendada no logon.
Set shell = CreateObject("WScript.Shell")
pasta = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
shell.Run """" & pasta & "\Servidor Permanente (loop).bat""", 0, False
