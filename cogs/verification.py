import discord
from discord.ext import commands
from discord import app_commands
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        # Ignore bot reactions
        if payload.user_id == self.bot.user.id:
            return
        
        try:
            # Load config
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return
            
            user = guild.get_member(payload.user_id)
            if not user:
                return
            
            # Check if this is a verification message
            channel = guild.get_channel(payload.channel_id)
            if not channel:
                return
            
            try:
                message = await channel.fetch_message(payload.message_id)
            except discord.NotFound:
                return
            
            # Check if message is from bot and contains verification embed
            if message.author != self.bot.user:
                return
            
            if not message.embeds:
                return
            
            embed = message.embeds[0]
            if "verification" not in embed.title.lower():
                return
            
            # Check if the reaction emoji matches
            emoji_str = str(payload.emoji)
            if emoji_str != config.get('verification_emoji', '✅'):
                return
            
            # Get verification role
            verification_role = guild.get_role(config['verification_role_id'])
            if not verification_role:
                logger.error(f"Verification role {config['verification_role_id']} not found in {guild.name}")
                return
            
            # Check if user already has the role
            if verification_role in user.roles:
                return
            
            # Add the role
            try:
                await user.add_roles(verification_role, reason="Verification reaction")
                logger.info(f"Verification role added to {user} ({user.id}) in {guild.name}")
                
                # Try to send DM confirmation
                try:
                    embed = discord.Embed(
                        title="✅ Verification Complete",
                        description=f"You have been successfully verified in **{guild.name}**!",
                        color=0x00ff00
                    )
                    await user.send(embed=embed)
                except discord.Forbidden:
                    pass  # User has DMs disabled
                    
            except discord.Forbidden:
                logger.error(f"Bot doesn't have permission to add roles in {guild.name}")
            except Exception as e:
                logger.error(f"Error adding verification role: {e}")
                
        except Exception as e:
            logger.error(f"Error in verification reaction handler: {e}")
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        # Ignore bot reactions
        if payload.user_id == self.bot.user.id:
            return
        
        try:
            # Load config
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return
            
            user = guild.get_member(payload.user_id)
            if not user:
                return
            
            # Check if this is a verification message
            channel = guild.get_channel(payload.channel_id)
            if not channel:
                return
            
            try:
                message = await channel.fetch_message(payload.message_id)
            except discord.NotFound:
                return
            
            # Check if message is from bot and contains verification embed
            if message.author != self.bot.user:
                return
            
            if not message.embeds:
                return
            
            embed = message.embeds[0]
            if "verification" not in embed.title.lower():
                return
            
            # Check if the reaction emoji matches
            emoji_str = str(payload.emoji)
            if emoji_str != config.get('verification_emoji', '✅'):
                return
            
            # Get verification role
            verification_role = guild.get_role(config['verification_role_id'])
            if not verification_role:
                logger.error(f"Verification role {config['verification_role_id']} not found in {guild.name}")
                return
            
            # Check if user has the role
            if verification_role not in user.roles:
                return
            
            # Remove the role
            try:
                await user.remove_roles(verification_role, reason="Verification reaction removed")
                logger.info(f"Verification role removed from {user} ({user.id}) in {guild.name}")
                
            except discord.Forbidden:
                logger.error(f"Bot doesn't have permission to remove roles in {guild.name}")
            except Exception as e:
                logger.error(f"Error removing verification role: {e}")
                
        except Exception as e:
            logger.error(f"Error in verification reaction remove handler: {e}")
    
    @app_commands.command(name="verification", description="Send verification message with reaction")
    @app_commands.describe(
        channel="Channel to send verification message (optional, defaults to current channel)"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def verification(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ):
        if channel is None:
            channel = interaction.channel
        
        # Check bot permissions in target channel
        bot_perms = channel.permissions_for(interaction.guild.me)
        if not bot_perms.send_messages or not bot_perms.embed_links:
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages or embed links in {channel.mention}!",
                ephemeral=True
            )
            return
        
        if not bot_perms.add_reactions:
            await interaction.response.send_message(
                f"❌ I don't have permission to add reactions in {channel.mention}!",
                ephemeral=True
            )
            return
        
        try:
            # Load config
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            # Get verification role
            verification_role = interaction.guild.get_role(config['verification_role_id'])
            if not verification_role:
                await interaction.response.send_message(
                    f"❌ Verification role not found! (ID: {config['verification_role_id']})",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="🔐 Server Verification",
                description=f"Al Verificarte aceptas las normas de conducta de el servidor y comportarte de manera adecuada.\n\n"
                           f"Para obtener acceso al servidor y recibir el rol {verification_role.mention}, "
                           f"reacciona con {config.get('verification_emoji', '✅')} a este mensaje.\n\n"
                           f"**Al verificarte obtienes:**\n"
                           f"• Acceso a los canales del servidor\n"
                           f"• Capacidad de participar en conversaciones\n"
                           f"• ¡Unirte a la comunidad!\n\n"
                           f"**Nota:** Si quitas tu reacción, perderás el rol.",
                color=0x3498db
            )
            embed.set_footer(
                text=f"Reacciona con {config.get('verification_emoji', '✅')} para verificarte",
                icon_url=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            # Send the message
            message = await channel.send(embed=embed)
            
            # Add the reaction
            await message.add_reaction(config.get('verification_emoji', '✅'))
            
            await interaction.response.send_message(
                f"✅ Verification message sent in {channel.mention}!",
                ephemeral=True
            )
            logger.info(f"Verification message created by {interaction.user} in {channel.name}")
            
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages in {channel.mention}!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error creating verification message: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while creating the verification message!",
                ephemeral=True
            )
    
    @app_commands.command(name="set-verification-role", description="Set the role for verification")
    @app_commands.describe(role="Role to assign when users verify")
    @app_commands.default_permissions(manage_roles=True)
    async def set_verification_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        # Check if bot can manage the role
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                f"❌ I can't manage {role.mention} because it's higher than or equal to my highest role!",
                ephemeral=True
            )
            return
        
        try:
            # Load and update config
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            config['verification_role_id'] = role.id
            
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=2)
            
            await interaction.response.send_message(
                f"✅ Verification role set to: {role.mention}",
                ephemeral=True
            )
            logger.info(f"Verification role set to {role.name} by {interaction.user}")
            
        except Exception as e:
            logger.error(f"Error setting verification role: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while setting the verification role!",
                ephemeral=True
            )
    
    @app_commands.command(name="set-verification-emoji", description="Set the emoji for verification")
    @app_commands.describe(emoji="Emoji to use for verification reactions")
    @app_commands.default_permissions(manage_roles=True)
    async def set_verification_emoji(
        self,
        interaction: discord.Interaction,
        emoji: str
    ):
        try:
            # Test if emoji is valid by trying to add it as a reaction
            test_message = await interaction.channel.send("Testing emoji...")
            await test_message.add_reaction(emoji)
            await test_message.delete()
            
            # Load and update config
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            config['verification_emoji'] = emoji
            
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=2)
            
            await interaction.response.send_message(
                f"✅ Verification emoji set to: {emoji}",
                ephemeral=True
            )
            logger.info(f"Verification emoji set to {emoji} by {interaction.user}")
            
        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ Invalid emoji! Please use a valid Unicode emoji or custom emoji from this server.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error setting verification emoji: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while setting the verification emoji!",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Verification(bot))
