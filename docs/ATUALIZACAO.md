# Atualizar a instalação Windows

Feche o servidor com Ctrl+C antes de atualizar. Abra `Atualizar.bat` na
raiz do projeto. O atalho busca `origin/main`, abre a `main` local e avança
somente para commits já publicados (**fast-forward**). Não cria commits
de merge e não exige `user.name` ou `user.email` para essa atualização.
Depois confere as dependências instaladas; reinicie o servidor ao concluir.

Commits de outras branches, como a branch de documentação do Claude,
continuam nessas branches. Atualizar abre a versão publicada na `main`;
arquivos exclusivos de outra branch deixam de aparecer na pasta de trabalho
até voltar para ela. `data/`, `saida/` e demais dados ignorados permanecem
locais. Arquivos novos que colidiriam com os publicados não são sobrescritos.

O atualizador interrompe antes de instalar dependências se encontrar
alterações versionadas, operação Git pendente, HEAD destacado, commits
exclusivos na `main` local ou erro de rede. Não guarda alterações
automaticamente, não descarta arquivos e não executa reset/rebase.
Revise o estado informado antes de prosseguir.

## Recuperar o atualizador antigo: Committer identity unknown

O atalho antigo usava `git pull origin main`. Esse comando integra a
`main` remota à branch que estiver aberta. Se precisar criar um merge e
o Git não tiver identidade configurada, aparece o erro
`Committer identity unknown`, mesmo após baixar todos os arquivos.
O download mostrado no log não confirma que a cópia de trabalho foi atualizada.

No **Git Bash aberto na pasta do projeto**, execute:

```bash
git switch main && git pull --ff-only origin main
```

O `&&` só permite a atualização se abrir a `main` com sucesso. Se terminar
sem erro, rode `Atualizar.bat` para conferir dependências e depois reinicie
o servidor. Não é necessário inventar um nome/e-mail ou alterar a configuração
global do Git para atualizar.

Se o comando recusar a troca ou o avanço, pare e confira:

```bash
git status --short --branch
git log --oneline --left-right main...origin/main
```

Alterações locais e commits divergentes precisam de revisão. Se houver
merge/rebase pendente, decida como concluir ou cancelar essa operação
após conferir o estado; o atualizador não toma essa decisão. Não use
`reset --hard` nem apague `data/` para resolver uma atualização.

## Verificação

```bash
git branch --show-current
git rev-parse HEAD origin/main
```

A branch deve ser `main` e os dois hashes devem coincidir após atualizar
sem erros. O atalho também imprime o hash curto do código instalado.
Essa verificação confirma a versão dos arquivos, não a emissão ou
homologação de rotinas no Domínio.
