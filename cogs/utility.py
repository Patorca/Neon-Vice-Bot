import discord
from discord.ext import commands
from discord import app_commands
import time
import logging

logger = logging.getLogger(__name__)

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="ping", description="Muestra la latencia del bot")
    async def ping(self, interaction: discord.Interaction):
        """Show bot latency and response time"""
        try:
            # Get Discord API latency
            api_latency = round(self.bot.latency * 1000, 2)
            
            # Measure response time
            start_time = time.time()
            
            embed = discord.Embed(
                title="🏓 Pong!",
                description="Información de latencia del bot",
                color=0x00ff00
            )
            
            embed.add_field(
                name="📡 Latencia API Discord",
                value=f"`{api_latency}ms`",
                inline=True
            )
            
            # Calculate response time after sending
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            end_time = time.time()
            response_time = round((end_time - start_time) * 1000, 2)
            
            # Update embed with response time
            embed.add_field(
                name="⚡ Tiempo de Respuesta",
                value=f"`{response_time}ms`",
                inline=True
            )
            
            # Add status indicator
            if api_latency < 100:
                status = "🟢 Excelente"
            elif api_latency < 200:
                status = "🟡 Bueno"
            elif api_latency < 300:
                status = "🟠 Regular"
            else:
                status = "🔴 Lento"
            
            embed.add_field(
                name="📊 Estado",
                value=status,
                inline=True
            )
            
            embed.set_footer(
                text=f"Bot: {self.bot.user.name}",
                icon_url=self.bot.user.display_avatar.url
            )
            
            # Edit the response with updated information
            await interaction.edit_original_response(embed=embed)
            
            logger.info(f"Ping command used by {interaction.user} - API: {api_latency}ms, Response: {response_time}ms")
            
        except Exception as e:
            logger.error(f"Error in ping command: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Error al obtener la latencia del bot!",
                    ephemeral=True
                )

    @app_commands.command(name="servidor_info", description="Muestra información detallada del servidor")
    async def servidor_info(self, interaction: discord.Interaction):
        """Show detailed server information"""
        try:
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message(
                    "❌ Este comando solo puede ser usado en un servidor!",
                    ephemeral=True
                )
                return

            # Get server statistics
            total_members = guild.member_count
            online_members = sum(1 for member in guild.members if member.status != discord.Status.offline)
            bot_count = sum(1 for member in guild.members if member.bot)
            human_count = total_members - bot_count
            
            # Get channel counts
            text_channels = len(guild.text_channels)
            voice_channels = len(guild.voice_channels)
            categories = len(guild.categories)
            
            # Get role count
            role_count = len(guild.roles)
            
            # Get boost information
            boost_level = guild.premium_tier
            boost_count = guild.premium_subscription_count
            
            # Create embed
            embed = discord.Embed(
                title=f"📊 Información del Servidor",
                description=f"**{guild.name}**",
                color=0x2f3136
            )
            
            # Add server icon
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            
            # Server basic info
            embed.add_field(
                name="🆔 ID del Servidor",
                value=f"`{guild.id}`",
                inline=True
            )
            
            embed.add_field(
                name="👑 Propietario",
                value=guild.owner.mention if guild.owner else "Desconocido",
                inline=True
            )
            
            embed.add_field(
                name="📅 Creado el",
                value=f"<t:{int(guild.created_at.timestamp())}:D>",
                inline=True
            )
            
            # Member statistics
            embed.add_field(
                name="👥 Miembros",
                value=f"**Total:** {total_members:,}\n**Humanos:** {human_count:,}\n**Bots:** {bot_count:,}\n**En línea:** {online_members:,}",
                inline=True
            )
            
            # Channel statistics
            embed.add_field(
                name="📁 Canales",
                value=f"**Texto:** {text_channels}\n**Voz:** {voice_channels}\n**Categorías:** {categories}",
                inline=True
            )
            
            # Role and boost info
            embed.add_field(
                name="🎭 Roles",
                value=f"{role_count}",
                inline=True
            )
            
            # Boost information
            boost_text = f"**Nivel:** {boost_level}\n**Boosts:** {boost_count}"
            embed.add_field(
                name="💎 Boosts",
                value=boost_text,
                inline=True
            )
            
            # Features
            features = []
            if guild.features:
                feature_names = {
                    'VERIFIED': '✅ Verificado',
                    'PARTNERED': '🤝 Asociado',
                    'COMMUNITY': '🌐 Comunidad',
                    'DISCOVERABLE': '🔍 Descubrible',
                    'VANITY_URL': '🔗 URL Personalizada',
                    'BANNER': '🖼️ Banner',
                    'ANIMATED_ICON': '🎬 Icono Animado'
                }
                for feature in guild.features:
                    if feature in feature_names:
                        features.append(feature_names[feature])
            
            if features:
                embed.add_field(
                    name="🌟 Características",
                    value="\n".join(features[:5]),  # Limit to 5 features
                    inline=True
                )
            
            # Verification level
            verification_levels = {
                discord.VerificationLevel.none: "Ninguna",
                discord.VerificationLevel.low: "Baja",
                discord.VerificationLevel.medium: "Media",
                discord.VerificationLevel.high: "Alta",
                discord.VerificationLevel.highest: "Muy Alta"
            }
            
            embed.add_field(
                name="🛡️ Verificación",
                value=verification_levels.get(guild.verification_level, "Desconocida"),
                inline=True
            )
            
            # Add footer
            embed.set_footer(
                text=f"Solicitado por {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"Server info command used by {interaction.user} in {guild.name}")
            
        except Exception as e:
            logger.error(f"Error in servidor_info command: {e}")
            await interaction.response.send_message(
                "❌ Error al obtener la información del servidor!",
                ephemeral=True
            )

    @app_commands.command(name="servidor_logo", description="Muestra el logo/icono del servidor")
    async def servidor_logo(self, interaction: discord.Interaction):
        """Show server logo/icon"""
        try:
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message(
                    "❌ Este comando solo puede ser usado en un servidor!",
                    ephemeral=True
                )
                return

            if not guild.icon:
                await interaction.response.send_message(
                    "❌ Este servidor no tiene un logo/icono configurado!",
                    ephemeral=True
                )
                return

            # Create embed with server icon
            embed = discord.Embed(
                title=f"🖼️ Logo del Servidor",
                description=f"**{guild.name}**",
                color=0x2f3136
            )
            
            # Set the server icon as the main image
            embed.set_image(url=guild.icon.url)
            
            # Add download links for different sizes
            icon_sizes = [256, 512, 1024, 2048]
            size_links = []
            
            for size in icon_sizes:
                icon_url = guild.icon.with_size(size).url
                size_links.append(f"[{size}x{size}]({icon_url})")
            
            embed.add_field(
                name="📥 Descargar en diferentes tamaños",
                value=" • ".join(size_links),
                inline=False
            )
            
            # Add server info
            embed.add_field(
                name="🆔 ID del Servidor",
                value=f"`{guild.id}`",
                inline=True
            )
            
            embed.add_field(
                name="📅 Servidor creado",
                value=f"<t:{int(guild.created_at.timestamp())}:D>",
                inline=True
            )
            
            # Add footer
            embed.set_footer(
                text=f"Solicitado por {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"Server logo command used by {interaction.user} in {guild.name}")
            
        except Exception as e:
            logger.error(f"Error in servidor_logo command: {e}")
            await interaction.response.send_message(
                "❌ Error al obtener el logo del servidor!",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Utility(bot))