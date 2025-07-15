import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import logging
from utils.helpers import load_config, save_config

logger = logging.getLogger(__name__)

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Send welcome message when a new member joins"""
        try:
            config = load_config()
            # Fix: Use 'servers' instead of 'guilds' to match config.json structure
            guild_config = config.get('servers', {}).get(str(member.guild.id), {})
            welcome_channel_id = guild_config.get('welcome_channel_id')
            
            if not welcome_channel_id:
                return
            
            welcome_channel = member.guild.get_channel(welcome_channel_id)
            
            if not welcome_channel:
                logger.error(f"Welcome channel {welcome_channel_id} not found in {member.guild.name}")
                return
            
            # Create the new Neon Vice RP welcome embed
            embed = discord.Embed(
                title="💎 ¡Bienvenid@ a **Neon Vice RP**! 🌆",
                description=f"🕶️ Un nuevo nivel de rol, estilo y libertad en Los Santos.\n\n"
                           f"👋 ¡Hola, {member.mention} nuevo ciudadano!\n"
                           f"Has llegado a **Neon Vice**, un servidor de GTA V Roleplay donde el estilo, la historia y la comunidad hacen la diferencia.\n"
                           f"Prepárate para vivir tu mejor versión en Los Santos. 🧬",
                color=0x9d4edd
            )
            
            # Add fields for better organization
            embed.add_field(
                name="🎯 ¿Qué puedes hacer en Neon Vice?",
                value="🧑‍💼 Unirte a bandas, mafias, cuerpos de seguridad o negocios legales\n"
                      "🏙️ Adquirir o alquilar locales → <#1392978362208882748>\n"
                      "🚗 Crear tu historia desde cero con libertad total\n"
                      "🎭 Disfrutar de eventos, tramas y rol dinámico\n"
                      "🆘 Recibir soporte directo de nuestro staff",
                inline=False
            )
            
            embed.add_field(
                name="📌 Canales importantes:",
                value="📜 **Reglas del servidor** → <#1392978340989767832>\n"
                      "📢 **Anuncios y novedades** → <#1392978364255440937>\n"
                      "✅ **Verificación obligatoria** → <#1392978339085549672>\n"
                      "📍 **Locales y propiedades disponibles** → <#1392978362208882748>\n"
                      "🎫 **Tickets de soporte** → <#1392978373101490258>",
                inline=False
            )
            
            embed.add_field(
                name="📝 Importante:",
                value="Antes de comenzar, asegúrate de leer las reglas y **verificarte** en <#1392978339085549672> para acceder a todo el servidor.\n"
                      "¿Tienes dudas? Abre un ticket en <#1392978373101490258> y te ayudaremos encantados.",
                inline=False
            )
            
            # Set thumbnail to user avatar
            embed.set_thumbnail(url=member.display_avatar.url)
            
            # Add server icon if available
            if member.guild.icon:
                embed.set_image(url=member.guild.icon.url)
            
            # Set footer
            embed.set_footer(
                text=f"🌆 ¡Nos vemos en las calles de Neon Vice RP! 🕶️ Tu historia empieza ahora.",
                icon_url=member.guild.icon.url if member.guild.icon else None
            )
            
            # Add timestamp
            embed.timestamp = discord.utils.utcnow()

            await welcome_channel.send(embed=embed)
            logger.info(f"Welcome message sent for {member} in {member.guild.name}")
            
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")

    @app_commands.command(name="configurar_bienvenida", description="Configura el canal de bienvenida para este servidor")
    @app_commands.describe(canal="Canal donde se enviarán los mensajes de bienvenida")
    async def set_welcome_channel(self, interaction: discord.Interaction, canal: discord.TextChannel):
        """Set the welcome channel for this server"""
        try:
            # Check if user has administrator permissions
            if not interaction.user.guild_permissions.administrator:
                embed = discord.Embed(
                    title="❌ Sin permisos",
                    description="Necesitas permisos de administrador para usar este comando.",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Load config
            config = load_config()
            
            # Initialize server config if not exists
            if 'servers' not in config:
                config['servers'] = {}
            if str(interaction.guild.id) not in config['servers']:
                config['servers'][str(interaction.guild.id)] = {}
            
            # Set welcome channel for this server
            config['servers'][str(interaction.guild.id)]['welcome_channel_id'] = canal.id
            
            # Save config
            if save_config(config):
                embed = discord.Embed(
                    title="✅ Canal de bienvenida configurado",
                    description=f"Los mensajes de bienvenida se enviarán en {canal.mention}",
                    color=0x00ff00
                )
                embed.add_field(
                    name="Servidor",
                    value=interaction.guild.name,
                    inline=True
                )
                embed.add_field(
                    name="Canal",
                    value=canal.mention,
                    inline=True
                )
                await interaction.response.send_message(embed=embed)
                logger.info(f"Welcome channel set to {canal.id} for guild {interaction.guild.id}")
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description="No se pudo guardar la configuración. Inténtalo de nuevo.",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error setting welcome channel: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="Ocurrió un error al configurar el canal de bienvenida.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="desactivar_bienvenida", description="Desactiva los mensajes de bienvenida en este servidor")
    async def disable_welcome(self, interaction: discord.Interaction):
        """Disable welcome messages for this server"""
        try:
            # Check if user has administrator permissions
            if not interaction.user.guild_permissions.administrator:
                embed = discord.Embed(
                    title="❌ Sin permisos",
                    description="Necesitas permisos de administrador para usar este comando.",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Load config
            config = load_config()
            
            # Check if server config exists
            if 'servers' not in config or str(interaction.guild.id) not in config['servers']:
                embed = discord.Embed(
                    title="ℹ️ Sin configuración",
                    description="Este servidor no tiene configurados mensajes de bienvenida.",
                    color=0x3498db
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Remove welcome channel configuration
            if 'welcome_channel_id' in config['servers'][str(interaction.guild.id)]:
                del config['servers'][str(interaction.guild.id)]['welcome_channel_id']
            
            # Clean up empty server config (but keep other settings)
            if 'welcome_channel_id' not in config['servers'][str(interaction.guild.id)] and len(config['servers'][str(interaction.guild.id)]) <= 1:
                # Only delete if no other important configs exist
                pass
            
            # Save config
            if save_config(config):
                embed = discord.Embed(
                    title="✅ Bienvenida desactivada",
                    description="Los mensajes de bienvenida han sido desactivados para este servidor.",
                    color=0x00ff00
                )
                await interaction.response.send_message(embed=embed)
                logger.info(f"Welcome messages disabled for guild {interaction.guild.id}")
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description="No se pudo guardar la configuración. Inténtalo de nuevo.",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error disabling welcome: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="Ocurrió un error al desactivar los mensajes de bienvenida.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="info_bienvenida", description="Muestra la configuración actual de bienvenida")
    async def welcome_info(self, interaction: discord.Interaction):
        """Show current welcome configuration"""
        try:
            config = load_config()
            guild_config = config.get('servers', {}).get(str(interaction.guild.id), {})
            welcome_channel_id = guild_config.get('welcome_channel_id')
            
            embed = discord.Embed(
                title="ℹ️ Configuración de Bienvenida",
                description=f"Configuración actual para **{interaction.guild.name}**",
                color=0x3498db
            )
            
            if welcome_channel_id:
                channel = self.bot.get_channel(welcome_channel_id)
                if channel:
                    embed.add_field(
                        name="Canal de Bienvenida",
                        value=channel.mention,
                        inline=False
                    )
                    embed.add_field(
                        name="Estado",
                        value="🟢 Activo",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="Canal de Bienvenida",
                        value=f"❌ Canal no encontrado (ID: {welcome_channel_id})",
                        inline=False
                    )
                    embed.add_field(
                        name="Estado",
                        value="🔴 Error",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="Canal de Bienvenida",
                    value="No configurado",
                    inline=False
                )
                embed.add_field(
                    name="Estado",
                    value="🔴 Desactivado",
                    inline=True
                )
            
            embed.set_footer(
                text="Use /configurar_bienvenida para configurar un canal"
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing welcome info: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="Ocurrió un error al mostrar la información de bienvenida.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="previsualizar_bienvenida", description="Muestra una vista previa del mensaje de bienvenida")
    async def preview_welcome(self, interaction: discord.Interaction):
        """Show a preview of the welcome message"""
        try:
            # Check if user has manage server permissions
            if not interaction.user.guild_permissions.manage_guild:
                embed = discord.Embed(
                    title="❌ Sin permisos",
                    description="Necesitas permisos para gestionar el servidor para usar este comando.",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Create preview embed (same as the actual welcome embed)
            preview_embed = discord.Embed(
                title="💎 ¡Bienvenid@ a **Neon Vice RP**! 🌆",
                description=f"🕶️ Un nuevo nivel de rol, estilo y libertad en Los Santos.\n\n"
                           f"👋 ¡Hola, {interaction.user.mention} nuevo ciudadano!\n"
                           f"Has llegado a **Neon Vice**, un servidor de GTA V Roleplay donde el estilo, la historia y la comunidad hacen la diferencia.\n"
                           f"Prepárate para vivir tu mejor versión en Los Santos. 🧬",
                color=0x9d4edd
            )
            
            # Add fields for better organization
            preview_embed.add_field(
                name="🎯 ¿Qué puedes hacer en Neon Vice?",
                value="🧑‍💼 Unirte a bandas, mafias, cuerpos de seguridad o negocios legales\n"
                      "🏙️ Adquirir o alquilar locales → <#1392978362208882748>\n"
                      "🚗 Crear tu historia desde cero con libertad total\n"
                      "🎭 Disfrutar de eventos, tramas y rol dinámico\n"
                      "🆘 Recibir soporte directo de nuestro staff",
                inline=False
            )
            
            preview_embed.add_field(
                name="📌 Canales importantes:",
                value="📜 **Reglas del servidor** → <#1392978340989767832>\n"
                      "📢 **Anuncios y novedades** → <#1392978364255440937>\n"
                      "✅ **Verificación obligatoria** → <#1392978339085549672>\n"
                      "📍 **Locales y propiedades disponibles** → <#1392978362208882748>\n"
                      "🎫 **Tickets de soporte** → <#1392978373101490258>",
                inline=False
            )
            
            preview_embed.add_field(
                name="📝 Importante:",
                value="Antes de comenzar, asegúrate de leer las reglas y **verificarte** en <#1392978339085549672> para acceder a todo el servidor.\n"
                      "¿Tienes dudas? Abre un ticket en <#1392978373101490258> y te ayudaremos encantados.",
                inline=False
            )
            
            # Set thumbnail to user avatar
            preview_embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            # Add server icon if available
            if interaction.guild.icon:
                preview_embed.set_image(url=interaction.guild.icon.url)
            
            # Set footer
            preview_embed.set_footer(
                text=f"🌆 ¡Nos vemos en las calles de Neon Vice RP! 🕶️ Tu historia empieza ahora.",
                icon_url=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            # Add timestamp
            preview_embed.timestamp = discord.utils.utcnow()

            # Send preview with notice
            preview_notice = discord.Embed(
                title="👁️ Vista Previa del Mensaje de Bienvenida",
                description="Este es el mensaje que verán los nuevos miembros cuando se unan al servidor:",
                color=0x3498db
            )
            
            await interaction.response.send_message(embed=preview_notice, ephemeral=True)
            await interaction.followup.send(embed=preview_embed, ephemeral=True)
            logger.info(f"Welcome preview shown to {interaction.user} in {interaction.guild.name}")
            
        except Exception as e:
            logger.error(f"Error showing welcome preview: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="Ocurrió un error al mostrar la vista previa.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Welcome(bot))