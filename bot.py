import os
import logging
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import uuid

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token
TOKEN = "8029507884:AAFWvki-SnwFZLqy6UDA-gBoW5weNiy_aSA"

# RemoveBG API key - using a free alternative that doesn't require API key
TEMP_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
os.makedirs(TEMP_FOLDER, exist_ok=True)

async def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "👋 Hi! I'm a Background Remover Bot.\n\n"
        "Just send me an image, and I'll remove the background for you!\n"
        "The processed image will have a watermark 'Edit By Kishan Soni'."
    )

async def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "How to use this bot:\n\n"
        "1. Send any image to me\n"
        "2. Wait a moment while I process it\n"
        "3. Receive your image with background removed\n"
        "4. Click the Download button to get your image"
    )

async def remove_background(update: Update, context: CallbackContext) -> None:
    """Remove background from the image sent by the user."""
    # Check if the message contains a photo
    if not update.message.photo:
        await update.message.reply_text("Please send an image to remove the background.")
        return

    # Get the largest photo (best quality)
    photo = update.message.photo[-1]
    
    # Send a processing message
    processing_message = await update.message.reply_text("Processing your image... Please wait.")
    
    try:
        # Get the file from Telegram
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()
        
        # Use remove.bg API alternative (using rembg library internally)
        output_image = await remove_bg_from_image(file_bytes)
        
        # Add watermark
        watermarked_image = add_watermark(output_image, "Edit By Kishan Soni")
        
        # Save the image with a unique filename
        unique_id = str(uuid.uuid4())
        output_path = os.path.join(TEMP_FOLDER, f"{unique_id}.png")
        watermarked_image.save(output_path)
        
        # Create download button
        keyboard = [
            [InlineKeyboardButton("Download Image", callback_data=f"download_{unique_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send the processed image
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_message.message_id)
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=open(output_path, 'rb'),
            caption="Background removed! Click the button below to download.",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_message.message_id)
        await update.message.reply_text(f"Sorry, there was an error processing your image. Please try again.")

async def button_callback(update: Update, context: CallbackContext) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    # Extract the unique ID from the callback data
    if query.data.startswith("download_"):
        unique_id = query.data.split("_")[1]
        image_path = os.path.join(TEMP_FOLDER, f"{unique_id}.png")
        
        if os.path.exists(image_path):
            # Send the document for download
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=open(image_path, 'rb'),
                filename="background_removed.png",
                caption="Here's your image with background removed!"
            )
        else:
            await query.edit_message_text(text="Sorry, the image is no longer available.")

async def remove_bg_from_image(image_data):
    """Remove background from image using rembg library."""
    try:
        # Import rembg here to avoid loading it at startup
        from rembg import remove
        import numpy as np
        from PIL import Image
        
        # Convert bytes to image
        input_image = Image.open(BytesIO(image_data))
        
        # Remove background
        output_image = remove(input_image)
        
        return output_image
    except Exception as e:
        # If there's any error, try to install rembg and try again
        import sys
        import subprocess
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "rembg[gpu]", "--upgrade"])
            
            # Try again after installation
            from rembg import remove
            input_image = Image.open(BytesIO(image_data))
            output_image = remove(input_image)
            
            return output_image
        except Exception as inner_e:
            # If still failing, try the CPU version
            subprocess.check_call([sys.executable, "-m", "pip", "install", "rembg", "--upgrade"])
            
            from rembg import remove
            input_image = Image.open(BytesIO(image_data))
            output_image = remove(input_image)
            
            return output_image

def add_watermark(image, watermark_text):
    """Add watermark to the image."""
    # Create a copy of the image
    watermarked = image.copy()
    
    # Create a drawing context
    draw = ImageDraw.Draw(watermarked)
    
    # Try to use a nice font, fall back to default if not available
    try:
        font_size = max(int(min(image.width, image.height) / 20), 20)  # Responsive font size
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    # Get text size
    try:
        text_width, text_height = draw.textsize(watermark_text, font=font)
    except:
        # For newer Pillow versions
        text_width, text_height = font.getsize(watermark_text) if hasattr(font, 'getsize') else (font_size * len(watermark_text) * 0.6, font_size)
    
    # Position the text at the bottom right with some padding
    x = image.width - text_width - 10
    y = image.height - text_height - 10
    
    # Add a semi-transparent background for the text
    padding = 5
    draw.rectangle(
        [(x - padding, y - padding), (x + text_width + padding, y + text_height + padding)],
        fill=(0, 0, 0, 100)
    )
    
    # Draw the text
    draw.text((x, y), watermark_text, fill=(255, 255, 255, 200), font=font)
    
    return watermarked

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.PHOTO, remove_background))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()