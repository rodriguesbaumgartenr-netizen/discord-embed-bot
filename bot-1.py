import os
import io
import re
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

import database as db

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


# ---------------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------------------------------------------------

def parse_cor(cor_str: str) -> int:
    try:
        return int(cor_str.replace("#", ""), 16)
    except (ValueError, AttributeError):
        return 0x5865F2


def resolver_emojis(texto: str, guild: discord.Guild) -> str:
    """Troca :nome_do_emoji: pelo emoji customizado do servidor, se existir."""
    if not texto or not guild:
        return texto

    def substituir(match):
        nome = match.group(1)
        emoji = discord.utils.get(guild.emojis, name=nome)
        return str(emoji) if emoji else match.group(0)

    return re.sub(r":([a-zA-Z0-9_~]{2,32}):", substituir, texto)


class EmbedState:
    """Guarda os dados de um embed enquanto ele está sendo montado/editado."""
    def __init__(self, titulo=None, descricao=None, cor=None, imagem=None, rodape=None,
                 campos=None, canal=None, imagem_bytes=None, imagem_filename=None,
                 autor_nome=None, autor_icone=None):
        self.titulo = titulo
        self.descricao = descricao
        self.cor = cor or 0x5865F2
        self.imagem = imagem
        self.rodape = rodape
        self.campos = campos or []
        self.canal = canal
        self.imagem_bytes = imagem_bytes
        self.imagem_filename = imagem_filename
        self.autor_nome = autor_nome
        self.autor_icone = autor_icone

    def to_dict(self):
        return {
            "titulo": self.titulo,
            "descricao": self.descricao,
            "cor": self.cor,
            # Imagens enviadas por upload não são salvas em modelos, só as por URL
            "imagem": self.imagem if not self.imagem_bytes else None,
            "rodape": self.rodape,
            "campos": self.campos,
        }


def construir_embed(state: EmbedState, guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(
        title=resolver_emojis(state.titulo, guild) if state.titulo else None,
        description=resolver_emojis(state.descricao, guild) if state.descricao else None,
        color=state.cor,
    )
    for campo in state.campos:
        embed.add_field(
            name=resolver_emojis(campo["nome"], guild),
            value=resolver_emojis(campo["valor"], guild),
            inline=campo.get("inline", False),
        )
    if state.imagem:
        embed.set_image(url=state.imagem)
    if state.rodape:
        embed.set_footer(text=resolver_emojis(state.rodape, guild))
    if state.autor_nome:
        embed.set_author(name=state.autor_nome, icon_url=state.autor_icone)
    return embed


# ---------------------------------------------------------------------------
# MODAIS (janelas de texto)
# ---------------------------------------------------------------------------

class CampoModal(discord.ui.Modal, title="Adicionar campo ao embed"):
    nome = discord.ui.TextInput(label="Nome do campo", max_length=256)
    valor = discord.ui.TextInput(label="Valor do campo", style=discord.TextStyle.paragraph, max_length=1024)
    lado_a_lado = discord.ui.TextInput(
        label="Lado a lado com outro campo? (sim/nao)", default="nao", max_length=3, required=False
    )

    def __init__(self, builder_view: "EmbedBuilderView"):
        super().__init__()
        self.builder_view = builder_view

    async def on_submit(self, interaction: discord.Interaction):
        inline = self.lado_a_lado.value.strip().lower() in ("sim", "s", "yes", "y")
        self.builder_view.state.campos.append({
            "nome": self.nome.value, "valor": self.valor.value, "inline": inline
        })
        embed_preview = construir_embed(self.builder_view.state, interaction.guild)
        await interaction.response.edit_message(embed=embed_preview, view=self.builder_view)


class SalvarModeloModal(discord.ui.Modal, title="Salvar como modelo"):
    nome = discord.ui.TextInput(label="Nome do modelo", placeholder="Ex: anuncio-manutencao", max_length=50)

    def __init__(self, builder_view: "EmbedBuilderView"):
        super().__init__()
        self.builder_view = builder_view

    async def on_submit(self, interaction: discord.Interaction):
        await db.salvar_modelo(interaction.guild.id, self.nome.value, self.builder_view.state.to_dict())
        await interaction.response.send_message(f"💾 Modelo **{self.nome.value}** salvo!", ephemeral=True)


# ---------------------------------------------------------------------------
# VIEW DE CONSTRUÇÃO/EDIÇÃO DO EMBED
# ---------------------------------------------------------------------------

class EmbedBuilderView(discord.ui.View):
    def __init__(self, state: EmbedState, modo: str, mensagem_alvo: discord.Message = None):
        super().__init__(timeout=600)
        self.state = state
        self.modo = modo  # "criar" ou "editar"
        self.mensagem_alvo = mensagem_alvo

        label_enviar = "Salvar alterações" if modo == "editar" else "Enviar"
        botao_enviar = discord.ui.Button(
            label=label_enviar, style=discord.ButtonStyle.success, emoji="✅", row=1
        )
        botao_enviar.callback = self.enviar_callback
        self.add_item(botao_enviar)

    @discord.ui.button(label="Adicionar Campo", style=discord.ButtonStyle.secondary, emoji="➕", row=0)
    async def add_campo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.state.campos) >= 25:
            await interaction.response.send_message("❌ Limite de 25 campos por embed atingido.", ephemeral=True)
            return
        await interaction.response.send_modal(CampoModal(self))

    @discord.ui.button(label="Salvar como modelo", style=discord.ButtonStyle.secondary, emoji="💾", row=0)
    async def salvar_modelo_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SalvarModeloModal(self))

    async def enviar_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed_final = construir_embed(self.state, interaction.guild)

        arquivo = None
        if self.state.imagem_bytes:
            arquivo = discord.File(io.BytesIO(self.state.imagem_bytes), filename=self.state.imagem_filename)

        if self.modo == "editar" and self.mensagem_alvo:
            try:
                if arquivo:
                    await self.mensagem_alvo.edit(embed=embed_final, attachments=[arquivo])
                else:
                    await self.mensagem_alvo.edit(embed=embed_final)
            except discord.Forbidden:
                await interaction.followup.send("❌ Não tenho permissão para editar essa mensagem.", ephemeral=True)
                return
            await interaction.followup.send("✅ Embed atualizado com sucesso!", ephemeral=True)
        else:
            destino = self.state.canal
            try:
                if arquivo:
                    await destino.send(embed=embed_final, file=arquivo, allowed_mentions=discord.AllowedMentions.none())
                else:
                    await destino.send(embed=embed_final, allowed_mentions=discord.AllowedMentions.none())
            except discord.Forbidden:
                await interaction.followup.send(f"❌ Não tenho permissão para enviar mensagens em {destino.mention}.", ephemeral=True)
                return
            await interaction.followup.send(f"✅ Embed enviado em {destino.mention}!", ephemeral=True)

        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.danger, emoji="❌", row=1)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Cancelado.", embed=None, view=None)
        self.stop()


# ---------------------------------------------------------------------------
# COMANDOS — grupo /embed (restrito a administradores)
# ---------------------------------------------------------------------------

embed_group = app_commands.Group(
    name="embed",
    description="Criar e gerenciar embeds",
    default_permissions=discord.Permissions(administrator=True),
)
modelo_group = app_commands.Group(name="modelo", description="Modelos de embed salvos", parent=embed_group)
recorrente_group = app_commands.Group(name="recorrente", description="Avisos automáticos repetidos", parent=embed_group)


@embed_group.command(name="criar", description="Cria um novo embed personalizado")
@app_commands.describe(
    titulo="Título do embed",
    descricao="Descrição do embed",
    cor="Cor em hexadecimal, ex: #00FF00 (opcional)",
    imagem_url="URL de uma imagem (opcional)",
    imagem_arquivo="Ou envie uma imagem da galeria do celular (opcional)",
    rodape="Texto do rodapé (opcional)",
    canal="Canal onde enviar (padrão: este canal)",
)
@app_commands.checks.has_permissions(administrator=True)
async def embed_criar(
    interaction: discord.Interaction,
    titulo: str,
    descricao: str,
    cor: str = "#5865F2",
    imagem_url: str = None,
    imagem_arquivo: discord.Attachment = None,
    rodape: str = None,
    canal: discord.TextChannel = None,
):
    await interaction.response.defer(ephemeral=True, thinking=True)

    imagem_bytes = None
    imagem_filename = None
    imagem_final = imagem_url

    if imagem_arquivo:
        if not imagem_arquivo.content_type or not imagem_arquivo.content_type.startswith("image/"):
            await interaction.followup.send("❌ O arquivo enviado precisa ser uma imagem.", ephemeral=True)
            return
        imagem_bytes = await imagem_arquivo.read()
        imagem_filename = imagem_arquivo.filename
        imagem_final = f"attachment://{imagem_filename}"

    state = EmbedState(
        titulo=titulo, descricao=descricao, cor=parse_cor(cor),
        imagem=imagem_final, rodape=rodape, canal=canal or interaction.channel,
        imagem_bytes=imagem_bytes, imagem_filename=imagem_filename,
        autor_nome=interaction.user.display_name, autor_icone=interaction.user.display_avatar.url,
    )

    view = EmbedBuilderView(state, modo="criar")
    embed_preview = construir_embed(state, interaction.guild)
    await interaction.followup.send(
        content="👀 **Pré-visualização** — adicione campos ou envie direto.",
        embed=embed_preview, view=view, ephemeral=True,
    )


@embed_group.command(name="editar", description="Edita um embed que o bot já enviou")
@app_commands.describe(
    canal="Canal onde está a mensagem",
    mensagem_id="ID da mensagem (ative o Modo Desenvolvedor no Discord pra copiar)",
)
@app_commands.checks.has_permissions(administrator=True)
async def embed_editar(interaction: discord.Interaction, canal: discord.TextChannel, mensagem_id: str):
    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        mensagem = await canal.fetch_message(int(mensagem_id))
    except (ValueError, discord.NotFound):
        await interaction.followup.send("❌ Mensagem não encontrada. Confira o ID e o canal.", ephemeral=True)
        return

    if mensagem.author.id != bot.user.id or not mensagem.embeds:
        await interaction.followup.send("❌ Essa mensagem não é um embed enviado por este bot.", ephemeral=True)
        return

    atual = mensagem.embeds[0]
    campos = [{"nome": f.name, "valor": f.value, "inline": f.inline} for f in atual.fields]

    state = EmbedState(
        titulo=atual.title, descricao=atual.description,
        cor=atual.color.value if atual.color else 0x5865F2,
        imagem=atual.image.url if atual.image else None,
        rodape=atual.footer.text if atual.footer else None,
        campos=campos, canal=canal,
    )

    view = EmbedBuilderView(state, modo="editar", mensagem_alvo=mensagem)
    embed_preview = construir_embed(state, interaction.guild)
    await interaction.followup.send(
        content="✏️ **Editando embed existente** — ajuste e clique em Salvar alterações.",
        embed=embed_preview, view=view, ephemeral=True,
    )


# ---------------------------------------------------------------------------
# COMANDOS — /embed modelo
# ---------------------------------------------------------------------------

@modelo_group.command(name="usar", description="Cria um embed a partir de um modelo salvo")
@app_commands.describe(nome="Nome do modelo salvo", canal="Canal onde enviar (padrão: este canal)")
@app_commands.checks.has_permissions(administrator=True)
async def modelo_usar(interaction: discord.Interaction, nome: str, canal: discord.TextChannel = None):
    dados = await db.obter_modelo(interaction.guild.id, nome)
    if not dados:
        await interaction.response.send_message(f"❌ Modelo `{nome}` não encontrado. Veja `/embed modelo listar`.", ephemeral=True)
        return

    state = EmbedState(
        titulo=dados["titulo"], descricao=dados["descricao"], cor=dados["cor"] or 0x5865F2,
        imagem=dados["imagem"], rodape=dados["rodape"], campos=dados["campos"],
        canal=canal or interaction.channel,
    )
    view = EmbedBuilderView(state, modo="criar")
    embed_preview = construir_embed(state, interaction.guild)
    await interaction.response.send_message(
        content=f"👀 **Modelo '{nome}' carregado** — ajuste se quiser e clique em Enviar.",
        embed=embed_preview, view=view, ephemeral=True,
    )


@modelo_group.command(name="listar", description="Lista os modelos de embed salvos")
@app_commands.checks.has_permissions(administrator=True)
async def modelo_listar(interaction: discord.Interaction):
    nomes = await db.listar_modelos(interaction.guild.id)
    if not nomes:
        await interaction.response.send_message("Nenhum modelo salvo ainda.", ephemeral=True)
        return
    texto = "\n".join(f"• `{n}`" for n in nomes)
    await interaction.response.send_message(f"📁 **Modelos salvos:**\n{texto}", ephemeral=True)


@modelo_group.command(name="remover", description="Remove um modelo salvo")
@app_commands.describe(nome="Nome do modelo a remover")
@app_commands.checks.has_permissions(administrator=True)
async def modelo_remover(interaction: discord.Interaction, nome: str):
    await db.remover_modelo(interaction.guild.id, nome)
    await interaction.response.send_message(f"🗑️ Modelo `{nome}` removido.", ephemeral=True)


# ---------------------------------------------------------------------------
# COMANDOS — /embed recorrente
# ---------------------------------------------------------------------------

@recorrente_group.command(name="criar", description="Cria um aviso que se repete a cada X minutos, sem marcar @everyone")
@app_commands.describe(
    titulo="Título do aviso",
    descricao="Texto do aviso",
    intervalo_minutos="A cada quantos minutos repetir",
    cor="Cor em hexadecimal (opcional)",
    imagem_url="URL de imagem (opcional)",
    rodape="Rodapé (opcional)",
    canal="Canal onde postar (padrão: este canal)",
)
@app_commands.checks.has_permissions(administrator=True)
async def recorrente_criar(
    interaction: discord.Interaction,
    titulo: str,
    descricao: str,
    intervalo_minutos: app_commands.Range[int, 1, 10080],
    cor: str = "#5865F2",
    imagem_url: str = None,
    rodape: str = None,
    canal: discord.TextChannel = None,
):
    destino = canal or interaction.channel
    dados = {
        "titulo": titulo, "descricao": descricao, "cor": parse_cor(cor),
        "imagem": imagem_url, "rodape": rodape, "campos": [],
    }
    recorrente_id = await db.criar_recorrente(interaction.guild.id, destino.id, dados, intervalo_minutos)
    await interaction.response.send_message(
        f"🔁 Aviso automático criado! Vai repetir em {destino.mention} a cada **{intervalo_minutos} minuto(s)**, "
        f"sem marcar ninguém. ID: `{recorrente_id}`\nUse `/embed recorrente parar` quando quiser encerrar.",
        ephemeral=True,
    )


@recorrente_group.command(name="listar", description="Lista os avisos automáticos ativos")
@app_commands.checks.has_permissions(administrator=True)
async def recorrente_listar(interaction: discord.Interaction):
    itens = await db.listar_recorrentes(interaction.guild.id)
    ativos = [i for i in itens if i["ativo"]]
    if not ativos:
        await interaction.response.send_message("Nenhum aviso automático ativo.", ephemeral=True)
        return
    texto = "\n".join(
        f"`{i['id']}` — **{i['titulo']}** — a cada {i['intervalo_minutos']} min — <#{i['canal_id']}>"
        for i in ativos
    )
    await interaction.response.send_message(f"🔁 **Avisos automáticos ativos:**\n{texto}", ephemeral=True)


@recorrente_group.command(name="parar", description="Para um aviso automático")
@app_commands.describe(id="ID do aviso (veja em /embed recorrente listar)")
@app_commands.checks.has_permissions(administrator=True)
async def recorrente_parar(interaction: discord.Interaction, id: int):
    await db.parar_recorrente(id)
    await interaction.response.send_message(f"⏹️ Aviso automático `{id}` parado.", ephemeral=True)


bot.tree.add_command(embed_group)


# ---------------------------------------------------------------------------
# TAREFA EM SEGUNDO PLANO — reenvia os avisos recorrentes no intervalo certo
# ---------------------------------------------------------------------------

@tasks.loop(seconds=30)
async def checar_recorrentes():
    agora = datetime.now(timezone.utc)
    ativos = await db.obter_recorrentes_ativos()

    for r in ativos:
        deve_enviar = True
        if r["ultimo_envio"]:
            ultimo = datetime.fromisoformat(r["ultimo_envio"])
            deve_enviar = (agora - ultimo).total_seconds() >= r["intervalo_minutos"] * 60
        if not deve_enviar:
            continue

        canal = bot.get_channel(r["canal_id"])
        if not canal:
            continue

        # Apaga a mensagem anterior antes de postar a nova, pra não acumular repetidas
        if r["ultima_mensagem_id"]:
            try:
                msg_antiga = await canal.fetch_message(r["ultima_mensagem_id"])
                await msg_antiga.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        state_temp = EmbedState(
            titulo=r["titulo"], descricao=r["descricao"], cor=r["cor"] or 0x5865F2,
            imagem=r["imagem"], rodape=r["rodape"], campos=r["campos"], canal=canal,
        )
        embed = construir_embed(state_temp, canal.guild)

        try:
            nova_msg = await canal.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            await db.atualizar_envio_recorrente(r["id"], nova_msg.id, agora.isoformat())
        except discord.Forbidden:
            continue


@checar_recorrentes.before_loop
async def antes_checar_recorrentes():
    await bot.wait_until_ready()


# ---------------------------------------------------------------------------
# EVENTOS E TRATAMENTO DE ERRO
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    await db.init_db()
    print(f"Bot conectado como {bot.user}")
    if not checar_recorrentes.is_running():
        checar_recorrentes.start()
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} comando(s) sincronizado(s).")
    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "🚫 Esse comando é só para administradores do servidor."
    else:
        msg = "❌ Ocorreu um erro ao executar o comando. Tente novamente."
        print(f"Erro não tratado: {error}")
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("Defina a variável de ambiente DISCORD_TOKEN com o token do seu bot.")
    bot.run(TOKEN)
