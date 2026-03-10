import os
import asyncio
import discord
from discord.ext import commands

from conversation_mode import conversation_mode
from orchestration.orchestrator import orchestrator
from core.logger import logger
from core.state import state_manager


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


async def _process_and_reply(message: discord.Message, text: str):
    async with message.channel.typing():
        try:
            result = await asyncio.to_thread(conversation_mode.process_message, text)

            if result["type"] in ("chat_reply", "clarification", "direct_answer"):
                response = result["response"]
                for chunk in _split(response, 1900):
                    await message.reply(chunk)
                return

            if result["type"] == "learn":
                domain = result.get("domain", "desconocido")
                num_bees = result.get("num_bees", 10)
                await message.reply(
                    f"Iniciando aprendizaje: {domain.upper()}\n"
                    f"Desplegando {num_bees} BEES investigadoras en paralelo..."
                )

                async def _learn_progress_discord(msg: str):
                    for chunk in _split(msg, 1900):
                        await message.channel.send(chunk)

                from memory.learning_engine import learning_engine
                try:
                    lr = await learning_engine.learn(
                        domain=domain,
                        num_bees=num_bees,
                        progress_callback=_learn_progress_discord,
                    )
                    level = lr.get("expertise_level", 0)
                    facts = "\n".join(f"• {f}" for f in lr.get("key_facts", [])[:8])
                    summary = (
                        f"Aprendizaje completado: {domain.upper()}\n"
                        f"Nivel: {level}/100 | Subtópicos: {lr.get('subtopics_covered', 0)}\n\n"
                        f"Síntesis:\n{lr.get('synthesis', '')[:600]}\n\n"
                        f"Hechos clave:\n{facts}"
                    )
                    for chunk in _split(summary, 1900):
                        await message.reply(chunk)
                except Exception as le:
                    await message.reply(f"Error en aprendizaje: {str(le)[:200]}")
                return

            if result["type"] == "autonomous_build":
                goal = result.get("goal", text)
                await message.reply(f"Builder autónomo activado.\nObjetivo: {goal[:200]}\n\nVoy trabajando, te mando updates.")

                async def _discord_progress(msg: str):
                    try:
                        for chunk in _split(msg, 1900):
                            await message.channel.send(chunk)
                    except Exception as pe:
                        logger.warning("discord progress error: %s", pe)

                from builder.autonomous_builder import autonomous_builder as _ab
                try:
                    build_result = await _ab.build(goal=goal, progress_callback=_discord_progress)
                    final_text = build_result.get("result", "Construcción completada.")
                    phases_ok = build_result.get("phases_completed", 0)
                    phases_total = build_result.get("phases_total", 0)
                    summary = f"Listo. {phases_ok}/{phases_total} fases completadas.\n\n{final_text}"
                    for chunk in _split(summary[:3800], 1900):
                        await message.reply(chunk)
                except Exception as ab_err:
                    await message.reply(f"Builder error: {str(ab_err)[:300]}")
                return

            # ── Wallet ────────────────────────────────────────────────────────
            if result["type"] == "wallet":
                await message.reply("Consultando wallets...")
                try:
                    from crypto.wallet_manager import wallet_manager
                    from crypto.price_feed import price_feed
                    wallet_manager.init_all_wallets()
                    balances, prices = await asyncio.gather(
                        wallet_manager.get_all_balances(),
                        price_feed.get_portfolio_prices(),
                    )
                    sym_prices = {
                        k: prices.get(k, {}).get("price", 0)
                        for k in ["ETH", "BNB", "SOL", "BTC"]
                    }
                    report = wallet_manager.format_balances_report(balances, sym_prices)
                    await message.reply(report)
                except Exception as e:
                    await message.reply(f"Error wallets: {e}")
                return

            # ── Price / Token ─────────────────────────────────────────────────
            if result["type"] == "price":
                token = result.get("token", "BTC,ETH,SOL,BNB")
                await message.reply("Consultando precios...")
                try:
                    from crypto.price_feed import price_feed
                    from crypto.analysis import analyzer
                    if len(token) > 20 and token.replace(".", "").isalnum():
                        info = await price_feed.get_token_info_dexscreener(token)
                        report = price_feed.format_token_info(info) if info else "Token no encontrado."
                    else:
                        symbols = [t.strip().upper() for t in token.replace(",", " ").split()]
                        if not symbols:
                            symbols = ["BTC", "ETH", "SOL", "BNB"]
                        prices = await price_feed.get_prices_coingecko(symbols)
                        report = price_feed.format_price_report(prices)
                        cg_map = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin"}
                        for sym in symbols[:1]:
                            cg_id = cg_map.get(sym)
                            if cg_id:
                                df = await analyzer.get_ohlcv_coingecko(cg_id, days=3)
                                if df is not None and len(df) >= 20:
                                    sig = analyzer.generate_signal(df)
                                    report += "\n\n" + analyzer.format_signal_report(sym, sig, prices.get(sym))
                    for chunk in _split(report, 1900):
                        await message.reply(chunk)
                except Exception as e:
                    await message.reply(f"Error precios: {e}")
                return

            # ── PumpFun ───────────────────────────────────────────────────────
            if result["type"] == "pumpfun":
                await message.reply("Escaneando PumpFun...")
                try:
                    from trading.pumpfun import pumpfun_scanner
                    opps = await pumpfun_scanner.scan_opportunities(min_score=40)
                    report = pumpfun_scanner.format_opportunities_report(opps)
                    for chunk in _split(report, 1900):
                        await message.reply(chunk)
                except Exception as e:
                    await message.reply(f"Error PumpFun: {e}")
                return

            # ── Trade ─────────────────────────────────────────────────────────
            if result["type"] == "trade":
                side = result.get("side", "BUY")
                token = result.get("token", "")
                amount = result.get("amount", 0.05)
                await message.reply(f"Ejecutando {side} de {token} por {amount} SOL...")
                try:
                    from trading.trading_engine import trading_engine
                    from crypto.wallet_manager import wallet_manager
                    wallet_manager.init_all_wallets()
                    sol_balance = await wallet_manager.get_balance_solana() or 0
                    signal_data = {"signal": side, "confidence": 75, "reason": "Orden manual desde Discord"}
                    token_info = {"price_usd": 0, "liquidity_usd": 999999, "name": token}
                    result_trade = await trading_engine.autonomous_trade(
                        token_mint=token,
                        signal_data=signal_data,
                        token_info=token_info,
                        portfolio_value_sol=sol_balance,
                        is_shitcoin=len(token) > 20,
                    )
                    report = trading_engine.format_trade_report(result_trade)
                    await message.reply(report)
                except Exception as e:
                    await message.reply(f"Error trade: {e}")
                return

            # ── Browser / Screenshot ──────────────────────────────────────────
            if result["type"] == "browser":
                url = result.get("url", "https://dexscreener.com")
                await message.reply(f"Abriendo {url}...")
                try:
                    from tools.browser_tool import browser_tool
                    screenshot_bytes = await browser_tool.screenshot(url)
                    if screenshot_bytes:
                        import io
                        f = discord.File(io.BytesIO(screenshot_bytes), filename="screenshot.png")
                        await message.reply(f"Screenshot de {url}", file=f)
                    else:
                        txt = await browser_tool.get_text(url)
                        await message.reply(f"No pude tomar screenshot.\n{txt[:1800] if txt else 'Sin contenido.'}")
                except Exception as e:
                    await message.reply(f"Error browser: {e}")
                return

            # ── Trading status / config ───────────────────────────────────────
            if result["type"] == "trading_status":
                from trading.autonomous_trader import autonomous_trader
                await message.reply(autonomous_trader.get_status())
                return

            if result["type"] == "trading_config":
                target_cfg = result.get("target", "")
                from trading.risk_manager import risk_manager
                if "pausa" in target_cfg.lower() or "desactiva" in target_cfg.lower():
                    risk_manager.update_config("enabled", False)
                    await message.reply("Trading autónomo pausado.")
                elif "activa" in target_cfg.lower() or "reanuda" in target_cfg.lower():
                    risk_manager.update_config("enabled", True)
                    await message.reply("Trading autónomo activado.")
                elif "simulaci" in target_cfg.lower() or "dry run" in target_cfg.lower():
                    current = risk_manager.config.get("dry_run", False)
                    risk_manager.update_config("dry_run", not current)
                    await message.reply(f"Modo: {'SIMULACION' if not current else 'REAL'}")
                else:
                    await message.reply(risk_manager.get_config_report())
                return

            if result["type"] == "task":
                orchestrator.initialize()
                output = await asyncio.wait_for(
                    asyncio.to_thread(orchestrator.process_task, result["task"]),
                    timeout=120,
                )
                if output is None:
                    await message.reply("La tarea tardó demasiado.")
                    return

                if output.get("type") == "image" and output.get("local_path"):
                    import os as _os
                    path = output["local_path"]
                    caption = output.get("revised_prompt", "")[:1000]
                    f = discord.File(path)
                    await message.reply(caption or "Imagen lista.", file=f)
                    _os.unlink(path)
                elif output.get("type") == "reminder":
                    seconds = output.get("seconds", 1800)
                    reminder_text = output.get("reminder_text", "")
                    channel = message.channel
                    asyncio.create_task(_discord_reminder(channel, reminder_text, seconds))
                    await message.reply(output.get("message", "Recordatorio configurado."))
                else:
                    response = output.get("message", str(output)[:1800])
                    for chunk in _split(response, 1900):
                        await message.reply(chunk)
        except Exception as e:
            logger.error("Discord process error: %s", e)
            await message.reply(f"Error: {e}")


async def _discord_reminder(channel: discord.TextChannel, text: str, seconds: int):
    await asyncio.sleep(seconds)
    await channel.send(f"Recordatorio: {text}")


def _split(text: str, max_len: int) -> list:
    chunks = []
    while len(text) > max_len:
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    if text:
        chunks.append(text)
    return chunks or [""]


@bot.event
async def on_ready():
    logger.info("BEEA Discord bot conectada como %s", bot.user)
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="la colmena"
    ))


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    if bot.user in message.mentions or isinstance(message.channel, discord.DMChannel):
        text = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if not text and message.attachments:
            text = "procesa este archivo"
        if text:
            await _process_and_reply(message, text)


@bot.command(name="bees")
async def bees_cmd(ctx, count: int, *, objective: str):
    """!bees <número> <objetivo> — lanza N BEES"""
    text = f"dame {count} bees que hagan: {objective}"
    await _process_and_reply(ctx.message, text)


@bot.command(name="imagen")
async def imagen_cmd(ctx, *, prompt: str):
    """!imagen <descripción> — genera una imagen con DALL-E"""
    await _process_and_reply(ctx.message, f"genera una imagen de {prompt}")


@bot.command(name="busca")
async def busca_cmd(ctx, *, query: str):
    """!busca <query> — búsqueda web"""
    await _process_and_reply(ctx.message, f"busca en internet: {query}")


@bot.command(name="traduce")
async def traduce_cmd(ctx, idioma: str, *, texto: str):
    """!traduce <idioma> <texto>"""
    await _process_and_reply(ctx.message, f"traduce al {idioma}: {texto}")


@bot.command(name="qr")
async def qr_cmd(ctx, *, content: str):
    """!qr <contenido> — genera un código QR"""
    await _process_and_reply(ctx.message, f"crea un qr de: {content}")


@bot.command(name="yt")
async def yt_cmd(ctx, url: str):
    """!yt <url> — resume un video de YouTube"""
    await _process_and_reply(ctx.message, f"resume este video de youtube: {url}")


@bot.command(name="corre")
async def corre_cmd(ctx, *, code: str):
    """!corre <código python> — ejecuta código"""
    clean = code.strip("`").strip()
    if clean.startswith("python"):
        clean = clean[6:].strip()
    await _process_and_reply(ctx.message, f"```python\n{clean}\n```")


@bot.command(name="sistema")
async def sistema_cmd(ctx):
    """!sistema — stats de CPU/memoria/disco"""
    from tools.system_monitor import get_system_stats
    stats = get_system_stats()
    await ctx.reply(stats)


@bot.command(name="aprende")
async def aprende_cmd(ctx, *, args: str):
    """!aprende <tema> [bees=N] — BEEA aprende un tema a fondo con BEES en paralelo"""
    import re as _re
    nums = _re.findall(r'\b(\d+)\s*bees?\b', args, _re.IGNORECASE)
    num_bees = int(nums[0]) if nums else 10
    domain = _re.sub(r'\d+\s*bees?', '', args, flags=_re.IGNORECASE).strip()

    await ctx.reply(
        f"Iniciando aprendizaje: {domain.upper()}\n"
        f"Desplegando {num_bees} BEES investigadoras en paralelo..."
    )

    async def _progress(msg: str):
        for chunk in _split(msg, 1900):
            await ctx.channel.send(chunk)

    from memory.learning_engine import learning_engine
    try:
        lr = await learning_engine.learn(domain=domain, num_bees=num_bees, progress_callback=_progress)
        level = lr.get("expertise_level", 0)
        facts = "\n".join(f"• {f}" for f in lr.get("key_facts", [])[:8])
        summary = (
            f"Aprendizaje completado: {domain.upper()}\n"
            f"Nivel: {level}/100 | Subtópicos: {lr.get('subtopics_covered', 0)}\n\n"
            f"Síntesis:\n{lr.get('synthesis', '')[:600]}\n\n"
            f"Hechos clave:\n{facts}"
        )
        for chunk in _split(summary, 1900):
            await ctx.reply(chunk)
    except Exception as e:
        await ctx.reply(f"Error: {str(e)[:200]}")


@bot.command(name="sabes")
async def sabes_cmd(ctx):
    """!sabes — muestra qué sabe BEEA y su nivel de expertise por dominio"""
    from memory.knowledge_base import knowledge_base
    summary = knowledge_base.get_full_knowledge_summary()
    for chunk in _split(summary, 1900):
        await ctx.reply(chunk)


@bot.command(name="build")
async def build_cmd(ctx, *, goal: str):
    """!build <objetivo> — Builder autónomo: construye cualquier cosa paso a paso"""
    await ctx.reply(f"Builder autónomo activado.\nObjetivo: {goal[:200]}\n\nVoy trabajando...")

    async def _progress(msg: str):
        try:
            for chunk in _split(msg, 1900):
                await ctx.channel.send(chunk)
        except Exception as e:
            logger.warning("build progress error: %s", e)

    from builder.autonomous_builder import autonomous_builder as _ab
    try:
        result = await _ab.build(goal=goal, progress_callback=_progress)
        final = result.get("result", "Completado.")
        phases_ok = result.get("phases_completed", 0)
        phases_total = result.get("phases_total", 0)
        summary = f"Listo. {phases_ok}/{phases_total} fases.\n\n{final}"
        for chunk in _split(summary[:3800], 1900):
            await ctx.reply(chunk)
    except Exception as e:
        await ctx.reply(f"Error en builder: {str(e)[:300]}")


@bot.command(name="ayuda")
async def ayuda_cmd(ctx):
    """!ayuda — lista de todos los comandos en embed rico"""
    embed = discord.Embed(
        title="BEEA — Panel de Comandos",
        description="Menciónala o escríbele en DM para hablar con lenguaje natural.",
        color=0xF7C948,
    )
    embed.add_field(
        name="💰 Crypto & Trading",
        value=(
            "`!wallet` — wallets y balances (BTC/ETH/SOL/Base/BSC)\n"
            "`!precio <token>` — precio + análisis técnico\n"
            "`!grafico <token>` — chart como imagen (RSI + Bollinger)\n"
            "`!pumpfun` — scanner de memecoins en PumpFun\n"
            "`!trading` — estado del trading autónomo\n"
            "`!alerta <token> <precio>` — crear alerta de precio\n"
            "`!compra <address> <sol>` — comprar via Jupiter\n"
            "`!vende <address>` — vender token en Solana"
        ),
        inline=False,
    )
    embed.add_field(
        name="🤖 IA & Herramientas",
        value=(
            "`!imagen <descripción>` — DALL-E 3\n"
            "`!busca <query>` — búsqueda web en tiempo real\n"
            "`!traduce <idioma> <texto>` — traducción\n"
            "`!screenshot <url>` — captura de pantalla web\n"
            "`!yt <url>` — resumen de YouTube\n"
            "`!qr <contenido>` — código QR\n"
            "`!corre <código>` — ejecutar Python"
        ),
        inline=False,
    )
    embed.add_field(
        name="🐝 BEES & Builder",
        value=(
            "`!bees <N> <objetivo>` — N agentes en paralelo\n"
            "`!aprende <tema>` — aprender a fondo con BEES\n"
            "`!sabes` — base de conocimiento actual\n"
            "`!build <objetivo>` — builder autónomo con updates"
        ),
        inline=False,
    )
    embed.add_field(
        name="⚙️ Sistema",
        value=(
            "`!sistema` — CPU / RAM / disco\n"
            "`!panel` — resumen completo del bot\n"
            "`!setup` — configurar canales del servidor\n"
            "`!ayuda` — este panel"
        ),
        inline=False,
    )
    embed.set_footer(text="Lenguaje natural: 'precio de BTC', 'mis wallets', 'estado del trading'")
    await ctx.reply(embed=embed)


@bot.command(name="panel")
async def panel_cmd(ctx):
    """!panel — estado completo del bot en embed"""
    import psutil
    embed = discord.Embed(title="BEEA — Estado del Sistema", color=0x00D4AA)

    try:
        from trading.autonomous_trader import autonomous_trader
        status = autonomous_trader.get_status()
        trading_line = (
            f"{'ACTIVO' if status.get('running') else 'PAUSADO'} | "
            f"{'Simulación' if status.get('dry_run') else 'REAL'} | "
            f"{status.get('total_trades', 0)} ops | "
            f"P&L: {status.get('total_pnl', 0):.4f} SOL"
        )
    except Exception:
        trading_line = "No disponible"

    try:
        from trading.price_alerts import price_alert_manager
        alerts_line = price_alert_manager.list_alerts()
    except Exception:
        alerts_line = "No disponible"

    try:
        from memory.knowledge_base import knowledge_base
        kb = knowledge_base.get_summary()
        kb_line = f"{kb.get('total_topics', 0)} temas, {kb.get('total_facts', 0)} hechos"
    except Exception:
        kb_line = "No disponible"

    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    embed.add_field(name="💻 Sistema",
                    value=f"CPU: {cpu:.1f}% | RAM: {ram.percent:.1f}% ({ram.used//1024//1024}MB/{ram.total//1024//1024}MB)",
                    inline=False)
    embed.add_field(name="🤖 Trading Autónomo", value=trading_line, inline=False)
    embed.add_field(name="🔔 Alertas Activas", value=alerts_line[:200], inline=False)
    embed.add_field(name="🧠 Base de Conocimiento", value=kb_line, inline=False)
    embed.set_footer(text="BEEA — leal a Álvaro / @xxvelonxx")
    await ctx.reply(embed=embed)


@bot.command(name="grafico")
async def grafico_cmd(ctx, symbol: str = "SOL"):
    """!grafico <token> — chart de precio como imagen"""
    await ctx.reply(f"Generando gráfico de {symbol.upper()}...")
    try:
        from trading.chart_generator import chart_generator
        img_bytes = await chart_generator.get_chart(symbol.upper(), days=7)
        if img_bytes:
            import io
            await ctx.reply(
                content=f"**{symbol.upper()}/USD — 7 días** (RSI + Bollinger + EMA)",
                file=discord.File(io.BytesIO(img_bytes), filename=f"{symbol.upper()}_chart.png"),
            )
        else:
            await ctx.reply(f"No pude obtener datos de precio para {symbol.upper()}.")
    except Exception as e:
        await ctx.reply(f"Error generando gráfico: {str(e)[:200]}")


@bot.command(name="alerta")
async def alerta_cmd(ctx, *, args: str = ""):
    """!alerta <token> <precio> — crear alerta. Ej: !alerta SOL 250"""
    if not args:
        await ctx.reply(
            "Uso: `!alerta <token> <precio>` — te aviso cuando suba a ese precio\n"
            "O: `!alerta <token> bajo <precio>` — te aviso cuando baje\n"
            "Ej: `!alerta SOL 250` o `!alerta BTC bajo 70000`"
        )
        return
    parts = args.strip().split()
    if len(parts) < 2:
        await ctx.reply("Formato: `!alerta SOL 250`")
        return
    symbol = parts[0].upper()
    direction = "above"
    price_str = parts[-1]
    if len(parts) >= 3 and parts[1].lower() in ("bajo", "baja", "abajo", "below"):
        direction = "below"
    try:
        target = float(price_str.replace(",", "").replace("$", ""))
    except ValueError:
        await ctx.reply("El precio debe ser un número. Ej: `!alerta SOL 250`")
        return
    try:
        from trading.price_alerts import price_alert_manager
        msg = price_alert_manager.add_alert(symbol, target, direction)
        await ctx.reply(msg)
    except Exception as e:
        await ctx.reply(f"Error configurando alerta: {e}")


@bot.command(name="setup")
@commands.has_permissions(manage_channels=True)
async def setup_server(ctx):
    """!setup — configura el servidor con todos los canales de BEEA"""
    guild = ctx.guild
    await ctx.reply("Configurando el servidor... Un momento.")

    SERVER_STRUCTURE = [
        {
            "name": "INICIO",
            "channels": [
                ("bienvenida", "Solo lectura — bienvenida al servidor de BEEA"),
                ("reglas", "Reglas del servidor"),
                ("anuncios", "Anuncios importantes de BEEA"),
            ],
        },
        {
            "name": "CRYPTO & TRADING",
            "channels": [
                ("precios", "Precios en tiempo real — usa !precio <token>"),
                ("graficos", "Gráficos de precio — usa !grafico <token>"),
                ("pumpfun", "Scanner de memecoins — usa !pumpfun"),
                ("trading-status", "Estado del trading autónomo — usa !trading"),
                ("alertas", "Alertas de precio — usa !alerta <token> <precio>"),
                ("wallets", "Ver balances — usa !wallet"),
                ("operaciones", "Log de operaciones del trading autónomo"),
            ],
        },
        {
            "name": "IA & HERRAMIENTAS",
            "channels": [
                ("imagenes", "Genera imágenes — !imagen <descripción>"),
                ("busquedas", "Búsqueda web — !busca <query>"),
                ("traducciones", "Traduce texto — !traduce <idioma> <texto>"),
                ("screenshots", "Capturas de pantalla — !screenshot <url>"),
                ("youtube", "Resumen de videos — !yt <url>"),
                ("codigo", "Ejecutar Python — !corre <código>"),
            ],
        },
        {
            "name": "BEES & BUILDER",
            "channels": [
                ("bees-lab", "Lanzar agentes BEES — !bees <N> <objetivo>"),
                ("builder", "Builder autónomo — !build <objetivo>"),
                ("aprendizaje", "Aprender temas — !aprende <tema>"),
                ("conocimiento", "Base de conocimiento — !sabes"),
            ],
        },
        {
            "name": "GENERAL",
            "channels": [
                ("chat", "Habla libremente con BEEA"),
                ("sistema", "Stats del sistema — !sistema"),
                ("logs", "Logs del bot"),
            ],
        },
    ]

    existing_categories = {c.name.upper(): c for c in guild.categories}
    existing_channels = {ch.name: ch for ch in guild.text_channels}
    created = 0

    for category_data in SERVER_STRUCTURE:
        cat_name = category_data["name"]
        if cat_name in existing_categories:
            category = existing_categories[cat_name]
        else:
            category = await guild.create_category(cat_name)
            created += 1

        for ch_name, topic in category_data["channels"]:
            if ch_name not in existing_channels:
                await guild.create_text_channel(ch_name, category=category, topic=topic)
                created += 1

    embed = discord.Embed(
        title="Servidor configurado",
        description=f"Se crearon {created} canales/categorías.\nTu servidor ya tiene la estructura completa de BEEA.",
        color=0x26a641,
    )
    embed.add_field(
        name="Categorías creadas",
        value="\n".join(f"• {c['name']}" for c in SERVER_STRUCTURE),
        inline=False,
    )
    await ctx.reply(embed=embed)


@setup_server.error
async def setup_server_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("Necesito permisos de Gestionar Canales para configurar el servidor.")


@bot.command(name="wallet")
async def wallet_cmd(ctx):
    """!wallet — ver wallets y balances"""
    await _process_and_reply(ctx.message, "muéstrame mis wallets con balances")


@bot.command(name="precio")
async def precio_cmd(ctx, *, token: str = "BTC ETH SOL"):
    """!precio <token> — precio + análisis técnico"""
    await _process_and_reply(ctx.message, f"precio de {token}")


@bot.command(name="pumpfun")
async def pumpfun_cmd(ctx):
    """!pumpfun — escanear oportunidades en pump.fun"""
    await _process_and_reply(ctx.message, "escanea oportunidades en pumpfun")


@bot.command(name="trading")
async def trading_cmd(ctx):
    """!trading — estado del trading autónomo"""
    await _process_and_reply(ctx.message, "estado del trading autónomo")


@bot.command(name="compra")
async def compra_cmd(ctx, token_address: str, sol_amount: float = 0.05):
    """!compra <address> <sol> — comprar token en Solana"""
    await _process_and_reply(ctx.message, f"compra {sol_amount} sol del token {token_address}")


@bot.command(name="vende")
async def vende_cmd(ctx, token_address: str):
    """!vende <address> — vender token en Solana"""
    await _process_and_reply(ctx.message, f"vende mis tokens de {token_address}")


@bot.command(name="screenshot")
async def screenshot_cmd(ctx, *, url: str):
    """!screenshot <url> — captura de pantalla de cualquier web"""
    await _process_and_reply(ctx.message, f"screenshot de {url}")


@bot.event
async def on_message_edit(before, after):
    pass


async def run_discord():
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        logger.warning("DISCORD_BOT_TOKEN no configurado — bot de Discord no iniciado")
        return
    try:
        await bot.start(token)
    except Exception as e:
        logger.error("Discord bot error: %s", e)
