import discord
from discord.ext import commands
import json
import logging

logger = logging.getLogger(__name__)

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Send welcome message when a new member joins"""
        try:
            # Load config
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            welcome_channel_id = config.get('welcome_channel_id', 1020374565710467163)
            welcome_channel = member.guild.get_channel(welcome_channel_id)
            
            if not welcome_channel:
                logger.error(f"Welcome channel {welcome_channel_id} not found in {member.guild.name}")
                return
            
            # Create welcome embed
            embed = discord.Embed(
                title="🎉 ¡Bienvenido a Neon Vice RP!",
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

async def setup(bot):
    await bot.add_cog(Welcome(bot))