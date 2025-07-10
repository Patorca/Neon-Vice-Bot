import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncio
import logging
import re
import json
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

async def load_config():
    """Load configuration from config.json"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}

async def save_config(config):
    """Save configuration to config.json"""
    try:
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return False

async def save_fivem_monitor_config(guild_id: int, channel_id: int, message_id: Optional[int] = None):
    """Save FiveM monitor configuration to config.json"""
    try:
        config = await load_config()
        guild_id_str = str(guild_id)
        
        if 'servers' not in config:
            config['servers'] = {}
        if guild_id_str not in config['servers']:
            config['servers'][guild_id_str] = {}
        
        config['servers'][guild_id_str]['fivem_status_channel_id'] = channel_id
        config['servers'][guild_id_str]['fivem_status_message_id'] = message_id
        config['servers'][guild_id_str]['fivem_monitor_active'] = True
        
        success = await save_config(config)
        if success:
            logger.info(f"FiveM monitor config saved to config.json: guild={guild_id}, channel={channel_id}, message={message_id}")
        return success
    except Exception as e:
        logger.error(f"Error saving FiveM monitor config: {e}")
        return False

async def get_fivem_monitor_config(guild_id: int):
    """Get FiveM monitor configuration from config.json"""
    try:
        config = await load_config()
        guild_id_str = str(guild_id)
        
        if ('servers' in config and 
            guild_id_str in config['servers'] and 
            config['servers'][guild_id_str].get('fivem_monitor_active', False)):
            
            return {
                'channel_id': config['servers'][guild_id_str].get('fivem_status_channel_id'),
                'message_id': config['servers'][guild_id_str].get('fivem_status_message_id')
            }
        return None
    except Exception as e:
        logger.error(f"Error getting FiveM monitor config: {e}")
        return None

async def disable_fivem_monitor_config(guild_id: int):
    """Disable FiveM monitor in config.json"""
    try:
        config = await load_config()
        guild_id_str = str(guild_id)
        
        if ('servers' in config and 
            guild_id_str in config['servers']):
            
            config['servers'][guild_id_str]['fivem_monitor_active'] = False
            if 'fivem_status_message_id' in config['servers'][guild_id_str]:
                del config['servers'][guild_id_str]['fivem_status_message_id']
            
            success = await save_config(config)
            if success:
                logger.info(f"FiveM monitor disabled in config.json for guild {guild_id}")
            return success
        return True
    except Exception as e:
        logger.error(f"Error disabling FiveM monitor config: {e}")
        return False

class FiveMStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.status_url = "https://status.cfx.re"
        self.active_monitors = {}  # guild_id: {'channel_id': int, 'message_id': int}
        self.last_status = {}
        self.setup_complete = False

    @commands.Cog.listener()
    async def on_ready(self):
        """Setup monitor when bot is ready"""
        if not self.setup_complete:
            logger.info("Setting up FiveM monitors from config.json...")
            await self.setup_monitor_from_config()
            self.setup_complete = True

    async def setup_monitor_from_config(self):
        """Load monitor configuration from config.json for all guilds"""
        try:
            loaded_monitors = 0
            # Load monitors for all guilds from config.json
            for guild in self.bot.guilds:
                monitor_config = await get_fivem_monitor_config(guild.id)
                if monitor_config:
                    channel_id = monitor_config['channel_id']
                    message_id = monitor_config['message_id']
                    
                    if not channel_id:
                        continue
                    
                    # Verificar que el canal y mensaje todavía existen
                    try:
                        channel = self.bot.get_channel(channel_id)
                        if channel and message_id:
                            try:
                                await channel.fetch_message(message_id)
                                self.active_monitors[guild.id] = {
                                    'channel_id': channel_id,
                                    'message_id': message_id,
                                    'guild_name': guild.name
                                }
                                loaded_monitors += 1
                                logger.info(f"Loaded FiveM monitor for guild {guild.id} ({guild.name}): channel={channel_id}, message={message_id}")
                            except discord.NotFound:
                                # Mensaje no encontrado, mantener canal pero limpiar mensaje
                                self.active_monitors[guild.id] = {
                                    'channel_id': channel_id,
                                    'message_id': None,
                                    'guild_name': guild.name
                                }
                                await save_fivem_monitor_config(guild.id, channel_id, None)
                                loaded_monitors += 1
                                logger.warning(f"FiveM status message not found for guild {guild.id} ({guild.name}), cleared message ID")
                        elif channel:
                            # Canal existe pero mensaje no, guardar solo el canal
                            self.active_monitors[guild.id] = {
                                'channel_id': channel_id,
                                'message_id': None,
                                'guild_name': guild.name
                            }
                            loaded_monitors += 1
                            logger.info(f"Loaded FiveM monitor for guild {guild.id} ({guild.name}): channel={channel_id}, message not found")
                        else:
                            # Canal no existe, desactivar monitor
                            await disable_fivem_monitor_config(guild.id)
                            logger.warning(f"FiveM status channel not found for guild {guild.id} ({guild.name}), disabling monitor")
                    except Exception as e:
                        logger.error(f"Error validating FiveM status message for guild {guild.id} ({guild.name}): {e}")

        except Exception as e:
            logger.error(f"Error loading FiveM monitor configs: {e}")

        # Start the monitor if we have any active monitors
        if self.active_monitors and not self.status_monitor.is_running():
            self.status_monitor.start()
            logger.info(f"Started FiveM status monitor for {loaded_monitors} guilds: {', '.join([info['guild_name'] for info in self.active_monitors.values()])}")
        elif loaded_monitors > 0:
            logger.info(f"FiveM status monitor already running for {loaded_monitors} guilds")

    def cog_unload(self):
        self.status_monitor.cancel()

    async def fetch_fivem_status(self) -> Dict[str, str]:
        """Fetch the current FiveM service status"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.status_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        return self.parse_status_content(content)
                    else:
                        logger.error(f"Error fetching status: HTTP {response.status}")
                        return {}
        except Exception as e:
            logger.error(f"Error fetching FiveM status: {e}")
            return {}

    def parse_status_content(self, content: str) -> Dict[str, str]:
        """Parse the status page content to extract service statuses"""
        status_dict = {}

        # Map of service patterns and their display names
        services = {
            "FiveM": "🎮 FiveM",
            "RedM": "🤠 RedM", 
            "Cfx.re Platform Server \\(FXServer\\)": "🖥️ FXServer",
            "Game Services": "🎯 Game Services",
            "CnL": "🔗 CnL",
            "Policy": "📋 Policy",
            "Keymaster": "🔑 Keymaster",
            "Web Services": "🌐 Web Services",
            "Forums": "💬 Forums",
            "Server List Frontend": "📋 Server List",
            "\"Runtime\"": "⚡ Runtime",
            "IDMS": "🆔 IDMS",
            "Portal": "🚪 Portal"
        }

        # Look for operational status indicators
        for service_pattern, display_name in services.items():
            # Create regex pattern to find service status
            pattern = rf"{service_pattern}.*?(?:Operational|Degraded Performance|Partial Outage|Major Outage|Maintenance)"
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)

            if match:
                text = match.group(0)
                if "Operational" in text:
                    status_dict[display_name] = "🟢 Operativo"
                elif "Degraded Performance" in text:
                    status_dict[display_name] = "🟡 Rendimiento Degradado"
                elif "Partial Outage" in text:
                    status_dict[display_name] = "🟠 Falla Parcial"
                elif "Major Outage" in text:
                    status_dict[display_name] = "🔴 Falla Mayor"
                elif "Maintenance" in text:
                    status_dict[display_name] = "🔧 Mantenimiento"
                else:
                    status_dict[display_name] = "❓ Desconocido"
            else:
                status_dict[display_name] = "❓ No disponible"

        # Check overall system status
        if "All Systems Operational" in content:
            status_dict["overall"] = "🟢 Todos los sistemas operativos"
        elif "Some Systems Experiencing Issues" in content:
            status_dict["overall"] = "🟡 Algunos sistemas con problemas"
        elif "Major Service Outage" in content:
            status_dict["overall"] = "🔴 Falla mayor del servicio"
        else:
            status_dict["overall"] = "❓ Estado general desconocido"

        return status_dict

    def create_status_embed(self, status_data: Dict[str, str]) -> discord.Embed:
        """Create an embed with the current FiveM status"""
        # Determine embed color based on overall status
        if "🟢" in status_data.get("overall", ""):
            color = 0x00ff00  # Green
        elif "🟡" in status_data.get("overall", ""):
            color = 0xffff00  # Yellow
        elif "🟠" in status_data.get("overall", ""):
            color = 0xff8000  # Orange
        elif "🔴" in status_data.get("overall", ""):
            color = 0xff0000  # Red
        else:
            color = 0x808080  # Gray

        embed = discord.Embed(
            title="📊 Estado de los Servidores FiveM",
            description=f"**Estado General:** {status_data.get('overall', 'Desconocido')}\n\n"
                       f"Información actualizada desde [status.cfx.re]({self.status_url})",
            color=color,
            timestamp=datetime.utcnow()
        )

        # Main gaming services
        gaming_services = []
        for service, status in status_data.items():
            if service in ["🎮 FiveM", "🤠 RedM", "🖥️ FXServer", "🎯 Game Services"]:
                gaming_services.append(f"{service}: {status}")

        if gaming_services:
            embed.add_field(
                name="🎮 **Servicios de Juego**",
                value="\n".join(gaming_services),
                inline=False
            )

        # Platform services
        platform_services = []
        for service, status in status_data.items():
            if service in ["🔗 CnL", "📋 Policy", "🔑 Keymaster", "🌐 Web Services"]:
                platform_services.append(f"{service}: {status}")

        if platform_services:
            embed.add_field(
                name="🛠️ **Servicios de Plataforma**",
                value="\n".join(platform_services),
                inline=False
            )

        # Community services
        community_services = []
        for service, status in status_data.items():
            if service in ["💬 Forums", "📋 Server List", "⚡ Runtime", "🆔 IDMS", "🚪 Portal"]:
                community_services.append(f"{service}: {status}")

        if community_services:
            embed.add_field(
                name="👥 **Servicios de Comunidad**",
                value="\n".join(community_services),
                inline=False
            )

        embed.set_footer(
            text="🔄 Actualizado automáticamente cada 5 minutos • PT Scripts BOT",
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )

        return embed

    @tasks.loop(minutes=5)
    async def status_monitor(self):
        """Monitor FiveM status every 5 minutes and update all active monitors"""
        try:
            if not self.active_monitors:
                logger.debug("Status monitor: No active monitors configured")
                return

            logger.info("Status monitor: Checking FiveM status...")
            status_data = await self.fetch_fivem_status()
            if not status_data:
                logger.error("Status monitor: Failed to fetch status data")
                return

            self.last_status = status_data

            # Update all active monitors
            for guild_id, monitor_info in list(self.active_monitors.items()):
                try:
                    channel_id = monitor_info['channel_id']
                    message_id = monitor_info.get('message_id')
                    guild_name = monitor_info.get('guild_name', f'Guild {guild_id}')
                    
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        logger.error(f"Status monitor: Channel {channel_id} not found for guild {guild_id} ({guild_name})")
                        # Remove from active monitors and disable in config
                        del self.active_monitors[guild_id]
                        await disable_fivem_monitor_config(guild_id)
                        continue

                    embed = self.create_status_embed(status_data)
                    
                    if message_id:
                        try:
                            message = await channel.fetch_message(message_id)
                            await message.edit(embed=embed)
                            logger.info(f"Status monitor: Updated message for guild {guild_id} ({guild_name})")
                        except discord.NotFound:
                            # Message was deleted, create a new one
                            logger.warning(f"Status monitor: Message not found for guild {guild_id} ({guild_name}), creating new one")
                            new_message = await channel.send(embed=embed)
                            self.active_monitors[guild_id]['message_id'] = new_message.id
                            await save_fivem_monitor_config(guild_id, channel_id, new_message.id)
                            logger.info(f"Status monitor: Created new message for guild {guild_id} ({guild_name})")
                        except discord.Forbidden:
                            logger.error(f"Status monitor: No permission to edit message in guild {guild_id} ({guild_name})")
                            # Try to create a new message instead
                            try:
                                new_message = await channel.send(embed=embed)
                                self.active_monitors[guild_id]['message_id'] = new_message.id
                                await save_fivem_monitor_config(guild_id, channel_id, new_message.id)
                                logger.info(f"Status monitor: Created new message due to permissions in guild {guild_id} ({guild_name})")
                            except Exception as e:
                                logger.error(f"Status monitor: Failed to create new message in guild {guild_id} ({guild_name}): {e}")
                        except Exception as e:
                            logger.error(f"Status monitor: Error updating message for guild {guild_id} ({guild_name}): {e}")
                    else:
                        # No message ID, create new message
                        try:
                            new_message = await channel.send(embed=embed)
                            self.active_monitors[guild_id]['message_id'] = new_message.id
                            await save_fivem_monitor_config(guild_id, channel_id, new_message.id)
                            logger.info(f"Status monitor: Created initial message for guild {guild_id} ({guild_name})")
                        except discord.Forbidden:
                            logger.error(f"Status monitor: No permission to send message in guild {guild_id} ({guild_name})")
                            # Disable the monitor for this guild
                            del self.active_monitors[guild_id]
                            await disable_fivem_monitor_config(guild_id)
                        except Exception as e:
                            logger.error(f"Status monitor: Error creating message for guild {guild_id} ({guild_name}): {e}")

                except Exception as e:
                    logger.error(f"Status monitor: Error processing guild {guild_id}: {e}")

        except Exception as e:
            logger.error(f"Status monitor: Unexpected error: {e}")

    @status_monitor.before_loop
    async def before_status_monitor(self):
        await self.bot.wait_until_ready()
        await self.setup_monitor_from_config()

    @app_commands.command(name="estado_fivem", description="Muestra el estado actual de los servidores de FiveM")
    async def fivem_status_command(self, interaction: discord.Interaction):
        """Show current FiveM server status"""
        try:
            await interaction.response.defer()

            status_data = await self.fetch_fivem_status()

            if not status_data:
                embed = discord.Embed(
                    title="❌ Error",
                    description="No se pudo obtener el estado de los servidores FiveM.",
                    color=0xff0000
                )
                await interaction.followup.send(embed=embed)
                return

            embed = self.create_status_embed(status_data)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in fivem_status_command: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="Ocurrió un error al obtener el estado de FiveM.",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="configurar_estado_fivem", description="Configura el monitoreo automático del estado de FiveM")
    @app_commands.describe(canal="Canal donde se mostrará el estado de FiveM")
    async def setup_fivem_monitor(self, interaction: discord.Interaction, canal: discord.TextChannel):
        """Setup automatic FiveM status monitoring"""
        try:
            # Check permissions
            if not interaction.user.guild_permissions.administrator:
                embed = discord.Embed(
                    title="❌ Sin permisos",
                    description="Necesitas permisos de administrador para usar este comando.",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            # Get initial status
            status_data = await self.fetch_fivem_status()
            if not status_data:
                embed = discord.Embed(
                    title="❌ Error",
                    description="No se pudo obtener el estado inicial de FiveM.",
                    color=0xff0000
                )
                await interaction.followup.send(embed=embed)
                return

            # Create and send the status message
            embed = self.create_status_embed(status_data)
            message = await canal.send(embed=embed)

            # Store the message and channel info in active monitors
            self.active_monitors[interaction.guild.id] = {
                'channel_id': canal.id,
                'message_id': message.id,
                'guild_name': interaction.guild.name
            }
            self.last_status = status_data

            # Save to config.json for persistence
            success = await save_fivem_monitor_config(interaction.guild.id, canal.id, message.id)
            if success:
                logger.info(f"FiveM monitor saved to config.json: guild={interaction.guild.id}, channel={canal.id}, message={message.id}")
            else:
                logger.error(f"Failed to save FiveM monitor to config.json for guild {interaction.guild.id}")
            
            # Start monitor if not running
            if not self.status_monitor.is_running():
                self.status_monitor.start()
                logger.info("Started FiveM status monitor")

            # Confirmation message
            confirmation_embed = discord.Embed(
                title="✅ Monitoreo configurado",
                description=f"El estado de FiveM se mostrará en {canal.mention} y se actualizará automáticamente cada 5 minutos.\n\n"
                           f"**El monitoreo persistirá** incluso si el bot se reinicia.",
                color=0x00ff00
            )
            await interaction.followup.send(embed=confirmation_embed)

            logger.info(f"FiveM status monitor configured for channel {canal.id}")

        except Exception as e:
            logger.error(f"Error in setup_fivem_monitor: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="Ocurrió un error al configurar el monitoreo de FiveM.",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="desactivar_estado_fivem", description="Desactiva el monitoreo automático del estado de FiveM")
    async def disable_fivem_monitor(self, interaction: discord.Interaction):
        """Disable automatic FiveM status monitoring"""
        try:
            # Check permissions
            if not interaction.user.guild_permissions.administrator:
                embed = discord.Embed(
                    title="❌ Sin permisos",
                    description="Necesitas permisos de administrador para usar este comando.",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Check if monitor is configured for this guild
            if interaction.guild.id not in self.active_monitors:
                embed = discord.Embed(
                    title="ℹ️ Sin configuración",
                    description="El monitoreo de FiveM no está actualmente configurado.",
                    color=0x3498db
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Remove from active monitors
            del self.active_monitors[interaction.guild.id]

            # Disable in config.json
            success = await disable_fivem_monitor_config(interaction.guild.id)
            if success:
                logger.info(f"FiveM monitor disabled in config.json for guild {interaction.guild.id}")
            else:
                logger.error(f"Failed to disable FiveM monitor in config.json for guild {interaction.guild.id}")

            # Stop monitor if no active monitors remain
            if not self.active_monitors and self.status_monitor.is_running():
                self.status_monitor.cancel()
                logger.info("Stopped FiveM status monitor - no active monitors")

            embed = discord.Embed(
                title="✅ Monitoreo desactivado",
                description="El monitoreo automático del estado de FiveM ha sido desactivado.",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed)

            logger.info("FiveM status monitor disabled")

        except Exception as e:
            logger.error(f"Error in disable_fivem_monitor: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="Ocurrió un error al desactivar el monitoreo de FiveM.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="forzar_actualizacion_fivem", description="Fuerza una actualización manual del estado de FiveM")
    async def force_update_fivem(self, interaction: discord.Interaction):
        """Force manual update of FiveM status"""
        try:
            # Check permissions
            if not interaction.user.guild_permissions.manage_guild:
                embed = discord.Embed(
                    title="❌ Sin permisos",
                    description="Necesitas permisos para gestionar el servidor para usar este comando.",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Check if monitor is configured for this guild
            if interaction.guild.id not in self.active_monitors:
                embed = discord.Embed(
                    title="ℹ️ Sin configuración",
                    description="El monitoreo de FiveM no está configurado. Usa `/configurar_estado_fivem` primero.",
                    color=0x3498db
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()

            # Force run the status monitor
            logger.info(f"Manual FiveM status update requested by {interaction.user}")
            await self.status_monitor()

            embed = discord.Embed(
                title="✅ Actualización forzada",
                description="Se ha forzado una actualización del estado de FiveM.",
                color=0x00ff00
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in force_update_fivem: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="Ocurrió un error al forzar la actualización.",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="info_monitor_fivem", description="Muestra información sobre el monitoreo de FiveM")
    async def monitor_info_fivem(self, interaction: discord.Interaction):
        """Show information about FiveM monitoring"""
        try:
            embed = discord.Embed(
                title="📊 Información del Monitor FiveM",
                color=0x3498db
            )

            if interaction.guild.id in self.active_monitors:
                monitor_info = self.active_monitors[interaction.guild.id]
                channel = self.bot.get_channel(monitor_info['channel_id'])
                embed.add_field(
                    name="Estado del Monitor",
                    value="🟢 Activo",
                    inline=True
                )
                embed.add_field(
                    name="Canal Configurado",
                    value=channel.mention if channel else f"❌ Canal no encontrado (ID: {monitor_info['channel_id']})",
                    inline=True
                )
                embed.add_field(
                    name="Frecuencia de Actualización",
                    value="⏰ Cada 5 minutos",
                    inline=True
                )
                embed.add_field(
                    name="ID del Mensaje",
                    value=f"`{monitor_info.get('message_id', 'Sin mensaje')}`",
                    inline=True
                )
                embed.add_field(
                    name="Loop Status",
                    value="🔄 Ejecutándose" if self.status_monitor.is_running() else "❌ Detenido",
                    inline=True
                )
                embed.add_field(
                    name="Próxima Actualización",
                    value=f"<t:{int(self.status_monitor.next_iteration.timestamp())}:R>" if self.status_monitor.next_iteration else "Desconocido",
                    inline=True
                )
            else:
                embed.add_field(
                    name="Estado del Monitor",
                    value="🔴 No configurado",
                    inline=False
                )
                embed.description = "El monitoreo automático de FiveM no está configurado.\nUsa `/configurar_estado_fivem` para configurarlo."

            embed.set_footer(text="Usa /forzar_actualizacion_fivem para una actualización manual")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error in monitor_info_fivem: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="Ocurrió un error al mostrar la información del monitor.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="estado_global_fivem", description="[DEV] Muestra el estado del monitoreo en todos los servidores")
    async def global_monitor_status(self, interaction: discord.Interaction):
        """Show global monitoring status across all servers"""
        try:
            # Only allow bot owner/admin to use this command
            if interaction.user.id != 462635310724022285:  # Your user ID
                embed = discord.Embed(
                    title="❌ Sin permisos",
                    description="Este comando está reservado para el desarrollador del bot.",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            embed = discord.Embed(
                title="🌍 Estado Global del Monitor FiveM",
                description=f"**Servidores activos:** {len(self.active_monitors)}\n"
                           f"**Monitor ejecutándose:** {'🟢 Sí' if self.status_monitor.is_running() else '🔴 No'}",
                color=0x3498db
            )

            if self.active_monitors:
                monitor_list = []
                for guild_id, monitor_info in self.active_monitors.items():
                    guild_name = monitor_info.get('guild_name', f'Guild {guild_id}')
                    channel_id = monitor_info['channel_id']
                    message_id = monitor_info.get('message_id', 'Sin mensaje')
                    
                    # Try to get channel name
                    channel = self.bot.get_channel(channel_id)
                    channel_name = channel.name if channel else f"Canal {channel_id}"
                    
                    monitor_list.append(f"**{guild_name}**\n"
                                       f"└ Canal: #{channel_name}\n"
                                       f"└ Mensaje: `{message_id}`")
                
                # Split into multiple fields if too long
                if len(monitor_list) <= 5:
                    embed.add_field(
                        name="📋 Servidores Configurados",
                        value="\n\n".join(monitor_list),
                        inline=False
                    )
                else:
                    # Split into chunks of 5
                    for i in range(0, len(monitor_list), 5):
                        chunk = monitor_list[i:i+5]
                        embed.add_field(
                            name=f"📋 Servidores Configurados ({i+1}-{min(i+5, len(monitor_list))})",
                            value="\n\n".join(chunk),
                            inline=False
                        )
            else:
                embed.add_field(
                    name="📋 Servidores Configurados",
                    value="No hay servidores configurados",
                    inline=False
                )

            if self.status_monitor.is_running() and self.status_monitor.next_iteration:
                embed.add_field(
                    name="⏰ Próxima Actualización",
                    value=f"<t:{int(self.status_monitor.next_iteration.timestamp())}:R>",
                    inline=True
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in global_monitor_status: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="Ocurrió un error al mostrar el estado global.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(FiveMStatus(bot))