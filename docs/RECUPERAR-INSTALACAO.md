# Recuperar código e Git sem apagar a instalação anterior

O diagnóstico do operador em 09/10/2026 confirmou web/index.html com
17.171 bytes e início preenchido com zeros; a resposta HTTPS era idêntica,
sem form-login. Por isso o servidor devolvia 200 OK mas a página ficava
branca. A tentativa de usar git archive HEAD também falhou: HEAD não era
um objeto válido. Cabeçalhos HTTP corretos não comprovam conteúdo correto.

Não foi determinada a origem da corrupção. O teste de regra no ESET não
corrigiu o arquivo local; retirar essa regra de teste após a recuperação.

## Recuperação pela cópia nova

1. Parar o servidor com Ctrl+C e aguardar a rotina atual terminar.
2. No CMD, entrar em uma pasta **fora** da instalação anterior e fazer
   um clone novo. Usar um nome livre; não clonar dentro de data/ da
   instalação que será recuperada.

   ```bat
   git clone --depth 1 --branch main https://github.com/financeirolucrattiva-web/dominio-automation-engine.git dominio-automation-engine-fonte-recuperacao
   ```

3. Executar o script da cópia nova, substituindo o argumento abaixo pelo
   caminho completo da instalação anterior:

   ```bat
   python dominio-automation-engine-fonte-recuperacao\scripts\recuperar_instalacao.py --destino "CAMINHO_COMPLETO_DA_INSTALACAO_ANTERIOR"
   ```

4. O script confere repositório, branch main, objetos Git e HTML do clone
   novo. Se alguma conferência falhar, interrompe antes de substituir o
   código anterior. Também recusa servidor/executor ativo e caminhos
   iguais/aninhados, worktrees, links no destino e arquivos incompatíveis.
5. Faz backup dos arquivos que serão substituídos e do Git anterior em
   data/recuperacao_codigo_*. Recupera o código versionado e um Git válido
   no caminho original da instalação. Dados em data/, PDFs em saida/,
   capturas, logs, .env, ambientes virtuais e arquivos não versionados
   permanecem locais. Não cria certificados nem reinstala dependências.
6. Reabrir o servidor pelo atalho original e atualizar o painel com
   Ctrl+F5. Conferir os cadastros e a versão da interface antes do teste.

O backup inclui modificações anteriores de arquivos do código; esses
arquivos não são reaplicados automaticamente sobre a main recuperada.
Configurações e commits do Git anterior permanecem no backup para revisão.
Falha durante a aplicação tenta reverter o código/Git para o estado anterior;
se aparecer erro, guardar o resultado e o backup para diagnóstico.

Testes automatizados usam repositórios Git reais locais e dados sintéticos,
incluindo HTML/HEAD zerados, executor ativo e falhas de aplicação. A execução
desse script no Windows do operador ainda precisa ser confirmada pelo log.

Após o Git ser recuperado, Atualizar.bat volta a usar a main com avanço
somente fast-forward. Não usar reset --hard, apagar data/ ou excluir o
backup para tentar destravar uma instalação corrompida.
