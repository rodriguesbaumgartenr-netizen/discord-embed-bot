import os
import discord
from discord import app_commands
from discord.ext import commands

# Pega o token do bot a partir de uma variável de ambiente (mais seguro)
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} comando(s) sincronizado(s).")
    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")


@bot.tree.command(name="embed", description="Cria um embed personalizado")
@app_commands.describe(
    titulo="Título do embed",
    descricao="Texto/descrição do embed",
    cor="Cor em hexadecimal, ex: #00FF00 (opcional)",
    imagem="URL de uma imagem para exibir (opcional)",
    rodape="Texto do rodapé (opcional)",
)
async def embed(
    interaction: discord.Interaction,
    titulo: str,
    descricao: str,
    cor: str = "#5865F2",
    imagem: str = None,
    rodape: str = None,
):
    # Converte a cor de hex string para inteiro
    try:
        cor_int = int(cor.replace("#", ""), 16)
    except ValueError:
        cor_int = 0x5865F2  # cor padrão (roxo Discord) se o usuário errar o formato

    embed_msg = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor_int,
    )

    if imagem:
        embed_msg.set_image(url=imagem)

    if rodape:
        embed_msg.set_footer(text=rodape)

    embed_msg.set_author(
        name=interaction.user.display_name,
        icon_url=interaction.user.display_avatar.url,
    )

    await interaction.response.send_message(embed=embed_msg)


if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("Defina a variável de ambiente DISCORD_TOKEN com o token do seu bot.")
    bot.run(TOKEN)
