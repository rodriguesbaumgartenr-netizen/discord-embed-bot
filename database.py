import json
import aiosqlite

DB_PATH = "embeds.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS modelos (
                guild_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                titulo TEXT,
                descricao TEXT,
                cor INTEGER,
                imagem TEXT,
                rodape TEXT,
                campos TEXT,
                PRIMARY KEY (guild_id, nome)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS recorrentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                canal_id INTEGER NOT NULL,
                titulo TEXT,
                descricao TEXT,
                cor INTEGER,
                imagem TEXT,
                rodape TEXT,
                campos TEXT,
                intervalo_minutos INTEGER NOT NULL,
                ultimo_envio TEXT,
                ultima_mensagem_id INTEGER,
                ativo INTEGER DEFAULT 1
            )
        """)
        await db.commit()


# ---------------------------------------------------------------------------
# MODELOS SALVOS
# ---------------------------------------------------------------------------

async def salvar_modelo(guild_id: int, nome: str, dados: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO modelos (guild_id, nome, titulo, descricao, cor, imagem, rodape, campos) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                guild_id, nome.lower().strip(), dados.get("titulo"), dados.get("descricao"),
                dados.get("cor"), dados.get("imagem"), dados.get("rodape"),
                json.dumps(dados.get("campos", [])),
            ),
        )
        await db.commit()


async def obter_modelo(guild_id: int, nome: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT titulo, descricao, cor, imagem, rodape, campos FROM modelos WHERE guild_id = ? AND nome = ?",
            (guild_id, nome.lower().strip()),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "titulo": row[0], "descricao": row[1], "cor": row[2],
            "imagem": row[3], "rodape": row[4], "campos": json.loads(row[5] or "[]"),
        }


async def listar_modelos(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT nome FROM modelos WHERE guild_id = ? ORDER BY nome", (guild_id,))
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def remover_modelo(guild_id: int, nome: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM modelos WHERE guild_id = ? AND nome = ?", (guild_id, nome.lower().strip()))
        await db.commit()


# ---------------------------------------------------------------------------
# AVISOS RECORRENTES
# ---------------------------------------------------------------------------

async def criar_recorrente(guild_id: int, canal_id: int, dados: dict, intervalo_minutos: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO recorrentes (guild_id, canal_id, titulo, descricao, cor, imagem, rodape, campos, intervalo_minutos) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                guild_id, canal_id, dados.get("titulo"), dados.get("descricao"),
                dados.get("cor"), dados.get("imagem"), dados.get("rodape"),
                json.dumps(dados.get("campos", [])), intervalo_minutos,
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def listar_recorrentes(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, titulo, canal_id, intervalo_minutos, ativo FROM recorrentes WHERE guild_id = ? ORDER BY id",
            (guild_id,),
        )
        rows = await cursor.fetchall()
        return [
            {"id": r[0], "titulo": r[1], "canal_id": r[2], "intervalo_minutos": r[3], "ativo": bool(r[4])}
            for r in rows
        ]


async def parar_recorrente(recorrente_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE recorrentes SET ativo = 0 WHERE id = ?", (recorrente_id,))
        await db.commit()


async def obter_recorrentes_ativos():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, guild_id, canal_id, titulo, descricao, cor, imagem, rodape, campos, "
            "intervalo_minutos, ultimo_envio, ultima_mensagem_id FROM recorrentes WHERE ativo = 1"
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0], "guild_id": r[1], "canal_id": r[2], "titulo": r[3], "descricao": r[4],
                "cor": r[5], "imagem": r[6], "rodape": r[7], "campos": json.loads(r[8] or "[]"),
                "intervalo_minutos": r[9], "ultimo_envio": r[10], "ultima_mensagem_id": r[11],
            }
            for r in rows
        ]


async def atualizar_envio_recorrente(recorrente_id: int, mensagem_id: int, timestamp_iso: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE recorrentes SET ultima_mensagem_id = ?, ultimo_envio = ? WHERE id = ?",
            (mensagem_id, timestamp_iso, recorrente_id),
        )
        await db.commit()
