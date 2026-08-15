# Bot Discord - Criador de Embeds

Bot com um comando slash `/embed` que cria mensagens embed personalizadas.

## Como usar o comando

No Discord, digite:
```
/embed titulo: Meu Título descricao: Minha descrição cor: #00FF00 imagem: https://link.png rodape: Feito por mim
```

Apenas `titulo` e `descricao` são obrigatórios. O resto é opcional.

## Passo a passo para colocar o bot no ar

### 1. Criar a aplicação no Discord
1. Acesse https://discord.com/developers/applications
2. Clique em "New Application" e dê um nome
3. Vá em "Bot" no menu lateral → "Add Bot"
4. Clique em "Reset Token" e copie o token (guarde em segredo!)
5. Em "Privileged Gateway Intents", não precisa ativar nenhum para este bot

### 2. Convidar o bot para o servidor
1. Vá em "OAuth2" → "URL Generator"
2. Marque os escopos: `bot` e `applications.commands`
3. Em permissões, marque: `Send Messages`, `Embed Links`, `Use Slash Commands`
4. Copie o link gerado, abra no navegador e escolha seu servidor

### 3. Subir para o GitHub (pelo celular)
1. Abra o app do GitHub (ou o site pelo navegador)
2. Crie um repositório novo (ex: "discord-embed-bot")
3. Envie os arquivos: `bot.py`, `requirements.txt`, `README.md`
   (NÃO envie o `.env` com o token real — use só o `.env.example`)

### 4. Deploy no Railway
1. Acesse https://railway.app e crie conta (dá pra logar com GitHub)
2. Clique em "New Project" → "Deploy from GitHub repo"
3. Selecione o repositório que você criou
4. Vá em "Variables" e adicione:
   - `DISCORD_TOKEN` = seu token copiado no passo 1
5. Em "Settings" → "Deploy", garanta que o comando de start seja:
   ```
   python bot.py
   ```
6. O Railway vai instalar as dependências do `requirements.txt` e rodar automaticamente

Pronto — o bot fica online 24h. Sempre que você atualizar o código no GitHub, o Railway re-implanta sozinho.
