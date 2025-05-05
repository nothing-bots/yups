#!/usr/bin/env python
#-*- coding: utf-8 -*-
"""
Russian fork by Vilfer
"""
import os
try:
    import keys
except ImportError:
    pass
from random import shuffle, choice
from datetime import datetime
from telegram import (ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup)
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler, PicklePersistence, CallbackQueryHandler)

import logging

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

GUESSING, CHOOSING_PLAYER = range(2)

WORDS = []
with open("words.txt", "r", encoding="UTF-8", errors="ignore") as file:
    for line in file.readlines():
        WORDS.append(line.replace("\n", ""))
shuffle(WORDS)


def show_rating(update, context):
    """
    Shows the rating of all the players in the chat
    """
    # If there already is a non-empty rating, show it
    if 'rating' in context.chat_data and context.chat_data['rating']:

        # Sorts the dict with the rating, turns it into a readable format
        rating = context.chat_data['rating']
        rating = {key: value for key, value in sorted(rating.items(), key=lambda x: x[1][1], reverse=True)}
        text = '\n'.join([f"{num + 1}. {item[1][0]}: {item[1][1]} Winnings" for num, item in enumerate(rating.items())])
        reply_text = f"Player rating in this chat:\n{text}"
        update.message.reply_text(reply_text, parse_mode="Markdown")

    else:
        update.message.reply_text("There is no rating in this chat")


def clear_rating(update, context):
    """
    Clears the current game rating board
    """
    if context.bot.getChatMember(update.message.chat.id, update.message.from_user.id).status == 'member':
        update.message.reply_text("The command is available only to administrators.")
        return
    if 'rating' in context.chat_data and context.chat_data['rating']:
        context.chat_data['rating'] = None
        update.message.reply_text("Rating cleared")
    else:
        update.message.reply_text("There is no rating in this chat")


def start(update, context):
    """
    Starts the new round of the game
    """
    if context.bot.getChatMember(update.message.chat.id, update.message.from_user.id).status == 'member':
        update.message.reply_text("The command is available only to administrators.")
        return
    if 'is_playing' in context.chat_data and context.chat_data['is_playing']:
        update.message.reply_text("The game has already begun")
        return

    logger.info("new game round")

    keyboard = [
        [InlineKeyboardButton("Look up the word", callback_data="look"),
         InlineKeyboardButton("Next word", callback_data="next")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Reads the user data and makes up a message with a link
    user_data = update['message'].from_user
    first_name = user_data['first_name'] if user_data['first_name'] is not None else ""
    last_name = f" {user_data['last_name']}" if user_data['last_name'] is not None else ""
    reply_text = f"[{first_name}{last_name}](tg://user?id={user_data['id']}) explains the word!"

    context.chat_data['is_playing'] = True
    context.chat_data['current_player'] = user_data['id']

    # Randomly chooses the word from a list and puts it into the chat data
    word_choice = choice(WORDS)
    context.chat_data['current_word'] = word_choice
    logger.info(f"Choose the word {word_choice}")

    update.message.reply_text(reply_text, reply_markup=reply_markup, parse_mode="Markdown")

    # Changing the state to GUESSING
    return GUESSING


def stop(update, context):
    """
    Stops the current game
    """
    if context.bot.getChatMember(update.message.chat.id, update.message.from_user.id).status == 'member':
        update.message.reply_text("Команда доступна только администраторам")
    elif 'is_playing' in context.chat_data and context.chat_data["is_playing"]:
        # Emptying all the temporary chat variables
        context.chat_data['current_player'] = None
        context.chat_data['current_word'] = None
        context.chat_data["is_playing"] = False
        update.message.reply_text("The game has been stopped")

        # Changing the state to CHOOSING_PLAYER
        return CHOOSING_PLAYER

    else:
        update.message.reply_text("There is no game to stop it")


def guesser(update, context):
    """
    Lets the players guess the word
    """

    # Getting the text the user sent and their data
    text = update.message.text.lower()
    user_data = update['message'].from_user

    # If the player trying to guess a word is not the current player and text is right, start a new round
    if user_data['id'] != context.chat_data["current_player"] and text == context.chat_data["current_word"]:

        # Change the rating, add 1 win for the winner
        rating = dict()
        if 'rating' in context.chat_data and context.chat_data['rating']:
            rating = context.chat_data['rating']

        first_name = user_data['first_name'] if user_data['first_name'] is not None else ""
        last_name = f" {user_data['last_name']}" if user_data['last_name'] is not None else ""

        if user_data['id'] in rating:
            rating[user_data['id']] = [f"[{first_name}{last_name}](tg://user?id={user_data['id']})",
                                       rating[user_data['id']][1] + 1]
        else:
            rating[user_data['id']] = [f"[{first_name}{last_name}](tg://user?id={user_data['id']})", 1]

        # Save the temporary variables, id of the winner and time of the win
        context.chat_data['rating'] = rating
        context.chat_data['winner'] = user_data['id']
        context.chat_data['win_time'] = datetime.now()

        logger.info(f"Player <{user_data['username']}> guessed the word <{context.chat_data['current_word']}>")

        keyboard = [[InlineKeyboardButton("I want to explain the following!", callback_data="next_player")]]

        reply_markup = InlineKeyboardMarkup(keyboard)
        reply_text = f"[{first_name}{last_name}](tg://user?id={user_data['id']}) guessed the word!"
        update.message.reply_text(reply_text, reply_markup=reply_markup, parse_mode="Markdown")

        # Changing the state to CHOOSING_PLAYER
        return CHOOSING_PLAYER

    else:
        logger.info(f"Player <{user_data['username']}> typed <{text}> and did not guess")
        return GUESSING


def next_player(update, context):
    """
    Starts the new game round based on who pressed the button
    """
    logger.info("Next player")
    query = update.callback_query
    if not('is_playing' in context.chat_data and context.chat_data['is_playing']):
        query.bot.answerCallbackQuery(callback_query_id=query.id, text="The game is currently unavailable", show_alert=True)
        return

        
    # If the user trying to press a button is the winner or if 5 seconds
    # for their unique opportuinity have passed, start a new round
    if (query.from_user['id'] == context.chat_data['winner'] or
            (datetime.now() - context.chat_data['win_time']).total_seconds() > 5):

        query.answer()
        keyboard = [
            [InlineKeyboardButton("Look up the word", callback_data="look"),
             InlineKeyboardButton("Next word", callback_data="next")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Update the temporary variables, edit the text
        first_name = query.from_user['first_name'] if query.from_user['first_name'] is not None else ""
        last_name = f" {query.from_user['last_name']}" if query.from_user['last_name'] is not None else ""
        reply_text = f"[{first_name}{last_name}](tg://user?id={query.from_user['id']}) explains the word!"

        context.chat_data["current_player"] = query.from_user['id']
        context.chat_data['current_word'] = choice(WORDS)

        query.edit_message_text(text=reply_text, parse_mode="Markdown")
        query.edit_message_reply_markup(reply_markup=reply_markup)

        # Change the state to GUESSING
        return GUESSING

    else:

        # Show an alert
        query.bot.answerCallbackQuery(callback_query_id=query.id,
                                      text="The winner has 5 seconds to choose, please wait.",
                                      show_alert=True)


def see_word(update, context):
    """
    Shows the current word only to the current player
    """
    logger.info("Look")
    query = update.callback_query

    # If the user trying to see the word does not have appropriate rights, show an alert,
    # otherwise show them the word
    if context.chat_data['current_player'] == query.from_user['id']:
        query.bot.answerCallbackQuery(callback_query_id=query.id,
                                      text=context.chat_data['current_word'],
                                      show_alert=True)
        logger.info("Current player saw the word")
    else:
        query.bot.answerCallbackQuery(callback_query_id=query.id,
                                      text="You can't watch!",
                                      show_alert=True)
        logger.info("Someone else asked to see the word, I didn't let them")

    # The state does not change from GUESSING
    return GUESSING


def next_word(update, context):
    """
    Chooses the next word
    """
    logger.info("Next")
    query = update.callback_query

    # If the user trying to skip the word does not have appropriate rights, show an alert,
    # otherwise skip the word and show it
    if context.chat_data['current_player'] == query.from_user['id']:
        context.chat_data['current_word'] = choice(WORDS)
        query.bot.answerCallbackQuery(callback_query_id=query.id,
                                      text=context.chat_data['current_word'],
                                      show_alert=True)
        logger.info("Current player skipped the word")
    else:
        query.bot.answerCallbackQuery(callback_query_id=query.id,
                                      text="You can't move on to the next word.!",
                                      show_alert=True)
        logger.info("Someone else asked to skip the word, I didn't let them")

    # The state does not change from GUESSING
    return GUESSING


def main():
    """
    Main bot function
    """
    token = os.environ['TOKEN']
    # Create the Updater and pass it your bot's token.
    updater = Updater(token, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Add conversation handler with the states CHOOSING, TYPING_CHOICE and TYPING_REPLY
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],

        states={
            CHOOSING_PLAYER: [CallbackQueryHandler(next_player, pattern="^next_player$"),
                              CommandHandler('stop', stop)],

            GUESSING: [MessageHandler(Filters.text, guesser),
                       CallbackQueryHandler(see_word, pattern="^look$"),
                       CallbackQueryHandler(next_word, pattern="^next$")],
        },
        fallbacks=[CommandHandler('start', start), CommandHandler('stop', stop)],
        name="my_conversation",
        per_user=False
    )

    dp.add_handler(CommandHandler('rating', show_rating))
    dp.add_handler(CommandHandler('clear_rating', clear_rating))

    dp.add_handler(conv_handler)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
