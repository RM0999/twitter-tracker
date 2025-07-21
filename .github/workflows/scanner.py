
# Twitter-to-Wallet Streamlit Dashboard
# Visual interface to match tweets with Solana wallet trades

import time
import requests
import sqlite3
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd

# ---------- CONFIGURATION ----------
TWITTER_USERNAME = "Cupseyy"
WALLET_ADDRESS = "suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK"
TWEET_LOOKBACK_MINUTES = 60
TRADE_LOOKBACK_MINUTES = 60

# ---------- DATABASE SETUP ----------
conn = sqlite3.connect("activity_log.db")
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS tweets (
    id TEXT PRIMARY KEY,
    timestamp TEXT,
    author TEXT,
    content TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    timestamp TEXT,
    token TEXT,
    amount REAL,
    matched_tweet_id TEXT
)
""")
conn.commit()

# ---------- TWITTER SCRAPER (SNSCRAPE) ----------
def fetch_recent_tweets(username):
    import snscrape.modules.twitter as sntwitter
    tweets = []
    cutoff = datetime.utcnow() - timedelta(minutes=TWEET_LOOKBACK_MINUTES)
    for tweet in sntwitter.TwitterUserScraper(username).get_items():
        if tweet.date < cutoff:
            break
        tweets.append({
            "id": str(tweet.id),
            "timestamp": tweet.date.isoformat(),
            "author": tweet.user.username,
            "content": tweet.content
        })
    return tweets

# ---------- SOLANA TRADE FETCH ----------
def fetch_recent_sol_trades(wallet):
    url = f"https://public-api.solscan.io/account/splTransfers?account={wallet}&limit=20"
    headers = {"accept": "application/json"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return []
    data = r.json()
    trades = []
    cutoff = datetime.utcnow() - timedelta(minutes=TRADE_LOOKBACK_MINUTES)
    for tx in data:
        ts = datetime.utcfromtimestamp(tx["blockTime"])
        if ts < cutoff:
            continue
        trades.append({
            "id": tx["signature"],
            "timestamp": ts.isoformat(),
            "token": tx["tokenSymbol"],
            "amount": float(tx["changeAmount"])/10**tx.get("decimals", 6)
        })
    return trades

# ---------- CORRELATION ENGINE ----------
def correlate_trades_with_tweets(tweets, trades):
    matched = []
    for trade in trades:
        trade_ts = datetime.fromisoformat(trade["timestamp"])
        for tweet in tweets:
            tweet_ts = datetime.fromisoformat(tweet["timestamp"])
            delta = abs((trade_ts - tweet_ts).total_seconds())
            if delta <= 1800:  # within 30 minutes
                trade["matched_tweet_id"] = tweet["id"]
                matched.append(trade)
                break
    return matched

# ---------- STREAMLIT UI ----------
st.set_page_config(page_title="Twitter Wallet Scanner", layout="wide")
st.title("📡 Twitter to Wallet Trade Tracker")

if st.button("🔁 Scan Now"):
    with st.spinner("Fetching recent tweets and trades..."):
        tweets = fetch_recent_tweets(TWITTER_USERNAME)
        trades = fetch_recent_sol_trades(WALLET_ADDRESS)
        matched_trades = correlate_trades_with_tweets(tweets, trades)

        # Save to DB
        for tweet in tweets:
            c.execute("INSERT OR IGNORE INTO tweets VALUES (?, ?, ?, ?)",
                      (tweet["id"], tweet["timestamp"], tweet["author"], tweet["content"]))
        for trade in matched_trades:
            c.execute("INSERT OR IGNORE INTO trades VALUES (?, ?, ?, ?, ?)",
                      (trade["id"], trade["timestamp"], trade["token"], trade["amount"], trade["matched_tweet_id"]))
        conn.commit()

        st.success(f"✅ Scanned {len(tweets)} tweets, {len(trades)} trades — {len(matched_trades)} matches found.")

        # Display results
        if matched_trades:
            df = pd.DataFrame(matched_trades)
            st.dataframe(df)
        else:
            st.info("No matched trades in this time window.")
else:
    st.info("Click the button above to start tracking @Cupseyy's tweets and wallet trades.")
