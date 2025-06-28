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
            guild_config = config.get('guilds', {}).get(str(member.guild.id), {})
            welcome_channel_id = guild_config.get('welcome_channel_id')
            
            # Check for global config (backwards compatibility)
            if not welcome_channel_id:
                welcome_channel_id = config.get('welcome_channel_id')
                if not welcome_channel_id:
                    return
            
            welcome_channel = member.guild.get_channel(welcome_channel_id)
            
            if not welcome_channel:
                logger.error(f"Welcome channel {welcome_channel_id} not found in {member.guild.name}")
                return
            
            # Create welcome embed
            embed = discord.Embed(
                title="🎉 ¡Bienvenido al servidor!",
                description=f"¡Hola {member.mention}! Te damos la bienvenida a **{member.guild.name}**.\n\n"
                           f"**Para empezar:**\n"
                           f"• Ve al canal de verificación y reacciona para obtener acceso\n"
                           f"• Lee las normas del servidor\n"
                           f"• ¡Presenta te y únete a la diversión!\n\n"
                           f"Si necesitas ayuda, no dudes en crear un ticket de soporte.\n\n"
                           f"¡Esperamos que disfrutes tu estancia aquí!",
                color=0x00ff7f
            )
            
            # Set thumbnail to user's avatar
            embed.set_thumbnail(url=member.display_avatar.url)
            
            # Set server icon as embed image if available
            if member.guild.icon:
                embed.set_image(url=member.guild.icon.url)
            
            embed.set_footer(
                text=f"Miembro #{len(member.guild.members)} • {member.guild.name}",
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
            
            # Initialize guild config if not exists
            if 'guilds' not in config:
                config['guilds'] = {}
            if str(interaction.guild.id) not in config['guilds']:
                config['guilds'][str(interaction.guild.id)] = {}
            
            # Set welcome channel for this guild
            config['guilds'][str(interaction.guild.id)]['welcome_channel_id'] = canal.id
            
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
            
            # Check if guild config exists
            if 'guilds' not in config or str(interaction.guild.id) not in config['guilds']:
                embed = discord.Embed(
                    title="ℹ️ Sin configuración",
                    description="Este servidor no tiene configurados mensajes de bienvenida.",
                    color=0x3498db
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Remove welcome channel configuration
            if 'welcome_channel_id' in config['guilds'][str(interaction.guild.id)]:
                del config['guilds'][str(interaction.guild.id)]['welcome_channel_id']
            
            # Clean up empty guild config
            if not config['guilds'][str(interaction.guild.id)]:
                del config['guilds'][str(interaction.guild.id)]
            
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
            guild_config = config.get('guilds', {}).get(str(interaction.guild.id), {})
            welcome_channel_id = guild_config.get('welcome_channel_id')
            
            # Check for global config (backwards compatibility)
            if not welcome_channel_id:
                welcome_channel_id = config.get('welcome_channel_id')
            
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

async def setup(bot):
    await bot.add_cog(Welcome(bot))