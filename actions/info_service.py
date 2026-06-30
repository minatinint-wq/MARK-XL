# info_service.py - Comprehensive information service
import requests
import json
import subprocess
import webbrowser
from urllib.parse import quote_plus
from datetime import datetime
import time
try:
    import feedparser  # For RSS fallback
    _FEEDPARSER_OK = True
except ImportError:
    _FEEDPARSER_OK = False

def _log(message: str, player=None) -> None:
    print(f"[Info] {message}")
    if player:
        try:
            player.write_log(f"[Info] {message}")
        except Exception:
            pass

def get_crypto_price(parameters: dict, player=None) -> str:
    """Get cryptocurrency prices"""
    coin = parameters.get("coin", "bitcoin").lower()
    currency = parameters.get("currency", "usd")

    try:
        # Use CoinGecko API (free, no API key needed)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies={currency}"
        headers = {"Accept": "application/json"}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if coin in data:
                price = data[coin].get(currency)
                if price:
                    # Get 24h change
                    url2 = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies={currency}&include_24hr_change=true"
                    resp2 = requests.get(url2, headers=headers, timeout=10)
                    if resp2.status_code == 200:
                        data2 = resp2.json()
                        change = data2[coin].get(f"{currency}_24h_change", 0)
                        emoji = "📈" if change >= 0 else "📉"
                        return f"{coin.title()}: ${price:,.2f} {emoji} ({change:+.2f}%)"
                    return f"{coin.title()}: ${price:,.2f}"
                return f"Could not find price for {coin}"
            return f"Coin not found: {coin}"
        else:
            # Fallback: open web search
            return f"Opening crypto prices for {coin}..."
    except Exception as e:
        _log(f"Crypto API error: {e}", player)
        return f"Could not get crypto price. Opening search..."

    # Fallback: open browser
    webbrowser.open(f"https://www.coingecko.com/en/price/{coin}")
    return f"Showing {coin} prices."

def get_stock_price(parameters: dict, player=None) -> str:
    """Get stock prices"""
    symbol = parameters.get("symbol", "").upper()

    if not symbol:
        return "Please provide a stock symbol."

    try:
        # Use Yahoo Finance (free)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if "chart" in data and "result" in data["chart"] and data["chart"]["result"]:
                result = data["chart"]["result"][0]
                meta = result.get("meta", {})
                price = meta.get("regularMarketPrice")
                prev = meta.get("previousClose")

                if price and prev:
                    change = price - prev
                    pct = (change / prev) * 100
                    emoji = "📈" if change >= 0 else "📉"
                    return f"{symbol}: ${price:.2f} {emoji} ({pct:+.2f}%)"
                return f"{symbol}: ${price:.2f}" if price else f"Could not get {symbol} price"
        return f"Could not find stock {symbol}"
    except Exception as e:
        _log(f"Stock API error: {e}", player)

    # Fallback
    webbrowser.open(f"https://finance.yahoo.com/quote/{symbol}")
    return f"Showing {symbol} stock."

def get_weather(parameters: dict, player=None) -> str:
    """Get weather forecast"""
    city = parameters.get("city", "")
    days = parameters.get("days", 1)

    if not city:
        return "Please provide a city name."

    try:
        # Use wttr.in (free, no API key)
        url = f"https://wttr.in/{quote_plus(city)}?format=j1"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            current = data.get("current_condition", [{}])[0]

            if current:
                temp = current.get("temp_C", "N/A")
                condition = current.get("weatherDesc", [{}])[0].get("value", "N/A")
                humidity = current.get("humidity", "N/A")
                wind = current.get("windspeedKmh", "N/A")

                result = f"🌤️ Weather in {city.title()}:"
                result += f"\nTemperature: {temp}°C"
                result += f"\nCondition: {condition}"
                result += f"\nHumidity: {humidity}%"
                result += f"\nWind: {wind} km/h"

                # Add forecast if requested
                if days > 1:
                    forecast = data.get("weather", [])
                    if len(forecast) > 1:
                        result += f"\n\n📅 Forecast:"
                        for f in forecast[1:days+1]:
                            date = f.get("date", "")
                            avgtemp = f.get("avgtempC", "N/A")
                            desc = f.get("hourly", [{}])[0].get("weatherDesc", [{}])[0].get("value", "")
                            result += f"\n{date}: {avgtemp}°C - {desc}"

                _log(result, player)
                return result
    except Exception as e:
        _log(f"Weather API error: {e}", player)

    # Fallback: open Google weather
    webbrowser.open(f"https://www.google.com/search?q=weather+{quote_plus(city)}")
    return f"Showing weather for {city}."

def get_news(parameters: dict, player=None) -> str:
    """Get latest news without opening browser"""
    topic = parameters.get("topic", "")
    lang = parameters.get("lang", "en")

    try:
        # Use GNews API (free tier - no API key needed for limited requests)
        if topic:
            url = f"https://gnews.io/api/v4/search?q={quote_plus(topic)}&lang={lang}&max=5&apikey=demo"
        else:
            url = f"https://gnews.io/api/v4/top-headlines?lang={lang}&max=5&apikey=demo"

        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            articles = data.get("articles", [])

            if articles:
                result = f"📰 News{': ' + topic if topic else ''}:\n\n"
                for i, article in enumerate(articles[:5], 1):
                    title = article.get("title", "")
                    source = article.get("source", {}).get("name", "")
                    url = article.get("url", "")
                    result += f"{i}. {title}\n   Source: {source}\n\n"

                _log(result, player)
                return result
            return f"No news found for '{topic}'"
        elif response.status_code == 401:
            # API key issue - try fallback to RSS or alternative
            return _get_news_fallback(topic)
        else:
            return _get_news_fallback(topic)
    except Exception as e:
        _log(f"News API error: {e}", player)
        return _get_news_fallback(topic)

def _get_news_fallback(topic: str) -> str:
    """Fallback news using free RSS feeds"""
    try:
        import feedparser
        if topic:
            # Use Google News RSS as fallback
            rss_url = f"https://news.google.com/rss/search?q={quote_plus(topic)}"
        else:
            rss_url = "https://news.google.com/rss"

        feed = feedparser.parse(rss_url)
        if feed.entries:
            result = f"📰 News{': ' + topic if topic else ''}:\n\n"
            for i, entry in enumerate(feed.entries[:5], 1):
                title = entry.get("title", "")
                result += f"{i}. {title}\n"
            result += "\n(Fallback RSS feed)"
            return result
    except:
        pass

    # Last resort - open browser
    if topic:
        webbrowser.open(f"https://news.google.com/search?q={quote_plus(topic)}")
        return f"Showing news about {topic}."
    webbrowser.open("https://news.google.com/")
    return "Showing latest news."

def get_sports_score(parameters: dict, player=None) -> str:
    """Get sports scores without opening browser"""
    sport = parameters.get("sport", "").lower()
    team = parameters.get("team", "").lower()

    # Special handling for football/soccer - use API-Football equivalent
    if sport in ["football", "soccer"]:
        return _get_football_scores(team, player)
    elif sport in ["basketball", "nba"]:
        return _get_nba_scores(player)
    elif sport == "tennis":
        return _get_tennis_scores(player)
    elif team:
        return _get_team_info(team, player)

    # Default - try to get today's sports headlines
    return _get_sports_headlines(player)

def _get_football_scores(team: str, player=None) -> str:
    """Get football scores - primary Brazilian leagues + Europe's top"""
    try:
        # Use public API for live scores
        url = "https://api.football-data.org/v4/matches"
        headers = {"X-Auth-Token": "demo"}  # Free tier token

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            matches = data.get("matches", [])

            # Filter to relevant matches (Brazil + top Europe)
            brazil_leagues = ["Serie A", "Copa do Brasil", "Brasileirão"]
            top_leagues = ["Premier League", "La Liga", " Bundesliga", "Serie A", "Ligue 1"]

            relevant = []
            for match in matches[:20]:
                comp = match.get("competition", {}).get("name", "")
                if any(l in comp for l in brazil_leagues + top_leagues):
                    home = match.get("homeTeam", {}).get("name", "")
                    away = match.get("awayTeam", {}).get("name", "")
                    score = match.get("score", {})
                    home_score = score.get("fullTime", {}).get("home", " - ")
                    away_score = score.get("fullTime", {}).get("away", " - ")
                    status = match.get("status", "")

                    if team and team not in home.lower() and team not in away.lower():
                        continue

                    relevant.append({
                        "comp": comp,
                        "home": home,
                        "away": away,
                        "score": f"{home_score}-{away_score}",
                        "status": status
                    })

            if relevant:
                result = "⚽ Today's Football:\n\n"
                for m in relevant[:8]:
                    status_emoji = "🔴" if m["status"] == "IN_PLAY" else "✅" if m["status"] == "FINISHED" else "🕐"
                    result += f"{status_emoji} {m['comp']}\n   {m['home']} {m['score']} {m['away']}\n\n"
                _log(result, player)
                return result
            return "No football matches today"
        else:
            return _get_football_fallback()
    except Exception as e:
        _log(f"Football API error: {e}", player)
        return _get_football_fallback()

def _get_football_fallback() -> str:
    """Fallback to Brazilian-focused scores"""
    try:
        # Use one of the free public APIs
        url = "https://site.api.espn.com/apis/site/v2/sports/soccer/bra.all/scoreboard"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            events = data.get("events", [])

            if events:
                result = "⚽ Brazil Football Today:\n\n"
                for event in events[:5]:
                    comp = event.get("league", {}).get("name", "")
                    competitors = event.get("competitions", [{}])[0].get("competitors", [])

                    home = competitors[0].get("team", {}).get("displayName", "")
                    away = competitors[1].get("team", {}).get("displayName", "")
                    home_score = competitors[0].get("score", "")
                    away_score = competitors[1].get("score", "")

                    result += f"• {comp}: {home} {home_score} x {away_score} {away_score}\n"

                return result
    except:
        pass

    webbrowser.open("https://ge.globo.com/futebol/")
    return "Opening Brazilian football coverage."

def _get_nba_scores(player=None) -> str:
    """Get NBA scores"""
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            events = data.get("events", [])

            if events:
                result = "🏀 NBA Today:\n\n"
                for event in events:
                    comp = event.get("league", {}).get("name", "")
                    competitors = event.get("competitions", [{}])[0].get("competitors", [])

                    home = competitors[0].get("team", {}).get("abbreviation", "")
                    away = competitors[1].get("team", {}).get("abbreviation", "")
                    home_score = competitors[0].get("score", "")
                    away_score = competitors[1].get("score", "")
                    status = event.get("status", {}).get("description", "")

                    result += f"• {home} {home_score} x {away} {away_score} ({status})\n"

                _log(result, player)
                return result
        return "No NBA games today"
    except Exception as e:
        _log(f"NBA API error: {e}", player)
        webbrowser.open("https://www.nba.com/scores")
        return "Showing NBA scores."

def _get_tennis_scores(player=None) -> str:
    """Get tennis scores/tournaments"""
    try:
        # Use tennis live data - public API
        url = "https://api.tennisapi.io/v1/competitions"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            # Return available tournaments
            result = "🎾 Tennis:\n\nActive tournaments:\n"
            for comp in data.get("competitions", [])[:5]:
                name = comp.get("name", "")
                result += f"• {name}\n"
            return result
    except:
        pass

    webbrowser.open("https://www.atptour.com/en/scores/current")
    return "Opening tennis scores."

def _get_team_info(team: str, player=None) -> str:
    """Get team information from TheSportsDB"""
    try:
        url = f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={quote_plus(team)}"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            teams = data.get("teams", [])

            if teams:
                t = teams[0]
                name = t.get("strTeam", "")
                league = t.get("strLeague", "")
                country = t.get("strCountry", "")
                badge = t.get("strTeamBadge", "")

                result = f"🔍 Team: {name}\n   League: {league}\n   Country: {country}"
                return result
        return f"Team not found: {team}"
    except Exception as e:
        _log(f"Team API error: {e}", player)

    webbrowser.open(f"https://www.google.com/search?q={quote_plus(team)}+score+today")
    return f"Showing {team} scores."

def _get_sports_headlines(player=None) -> str:
    """Get general sports news headlines"""
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary"
        response = requests.get(url, timeout=10)

        # Even if we can't get specific data, we try a general sports API
        # For now return a message about what we can query
        return "I can get scores for: Football/Soccer, Basketball/NBA, Tennis. Which sport would you like?"
    except:
        return "Sports scores unavailable. Try specifying a sport: football, basketball, or tennis."

def get_currency_exchange(parameters: dict, player=None) -> str:
    """Get currency exchange rates"""
    from_curr = parameters.get("from", "USD").upper()
    to_curr = parameters.get("to", "BRL").upper()
    amount = parameters.get("amount", 1)

    try:
        # Use ExchangeRate-API (free)
        url = f"https://api.exchangerate-api.com/v4/latest/{from_curr}"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            rates = data.get("rates", {})
            if to_curr in rates:
                rate = rates[to_curr]
                result = amount * rate
                return f"{amount} {from_curr} = {result:.2f} {to_curr} (Rate: 1 {from_curr} = {rate:.4f} {to_curr})"
        return f"Could not get exchange rate {from_curr} to {to_curr}"
    except Exception as e:
        _log(f"Exchange API error: {e}", player)

    webbrowser.open(f"https://www.google.com/search?q={from_curr}+to+{to_curr}+exchange+rate")
    return f"Showing {from_curr} to {to_curr} rates."

def get_definition(parameters: dict, player=None) -> str:
    """Get word definition"""
    word = parameters.get("word", "")

    if not word:
        return "Please provide a word to define."

    try:
        # Use Free Dictionary API
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list):
                first = data[0]
                meanings = first.get("meanings", [])

                result = f"📖 Definition of '{word}':\n\n"
                for meaning in meanings[:2]:
                    part = meaning.get("partOfSpeech", "")
                    definitions = meaning.get("definitions", [])
                    if definitions:
                        defn = definitions[0].get("definition", "")
                        result += f"• ({part}) {defn}\n"

                _log(result, player)
                return result
        return f"Could not find definition for '{word}'"
    except Exception as e:
        _log(f"Dictionary API error: {e}", player)

    webbrowser.open(f"https://www.google.com/search?q=define+{quote_plus(word)}")
    return f"Showing definition for {word}."

def get_trivia(parameters: dict, player=None) -> str:
    """Get random trivia"""
    try:
        url = "https://opentdb.com/api.php?amount=1&type=multiple"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data.get("results"):
                q = data["results"][0]
                question = q.get("question", "")
                correct = q.get("correct_answer", "")
                incorrect = q.get("incorrect_answers", [])

                # Decode HTML entities
                import html
                question = html.unescape(question)
                correct = html.unescape(correct)

                result = f"❓ Trivia:\n{question}\n\nAnswer: {correct}"
                _log(result, player)
                return result
    except Exception as e:
        _log(f"Trivia API error: {e}", player)

    return "Could not get trivia."

def get_fact(parameters: dict, player=None) -> str:
    """Get random fact"""
    try:
        url = "https://uselessfacts.jsph.pl/api/v2/facts/random?language=en"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            fact = data.get("text", "")
            _log(f"💡 Fact: {fact}", player)
            return f"💡 {fact}"
    except Exception as e:
        _log(f"Fact API error: {e}", player)

    return "Could not get fact."

def get_population(parameters: dict, player=None) -> str:
    """Get country population"""
    country = parameters.get("country", "")

    if not country:
        return "Please provide a country name."

    try:
        # Use WorldBank API
        url = f"https://api.worldbank.org/v2/country/{quote_plus(country)}?format=json"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if len(data) > 1 and data[1]:
                pop = data[1][0].get("population")
                if pop:
                    return f"Population of {country.title()}: {pop:,}"
        return f"Could not find population for {country}"
    except Exception as e:
        _log(f"Population API error: {e}", player)

    webbrowser.open(f"https://www.google.com/search?q=population+{quote_plus(country)}")
    return f"Showing population for {country}."


# ========== BRAZILIAN MARKET (B3) ==========

def get_brazilian_stocks(parameters: dict, player=None) -> str:
    """Get Brazilian B3 stocks without opening browser"""
    symbol = parameters.get("symbol", "").upper().strip()
    action = parameters.get("action", "").lower()

    # Default stocks to show if no specific symbol
    default_stocks = ["PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "WEGE3", "MGLU3", "JBSS3"]

    # Map common Brazilian stocks to Yahoo Finance symbols
    stock_map = {
        "PETR4": "PETR4.SA", "PETR3": "PETR3.SA", "PETROBRAS": "PETR4.SA",
        "VALE3": "VALE3.SA", "VALE": "VALE3.SA",
        "ITUB4": "ITUB4.SA", "ITAU": "ITUB4.SA",
        "BBDC4": "BBDC4.SA", "BRADESCO": "BBDC4.SA",
        "ABEV3": "ABEV3.SA", "AMBEV": "ABEV3.SA",
        "WEGE3": "WEGE3.SA", "WEG": "WEGE3.SA",
        "MGLU3": "MGLU3.SA", "MAGAZINE LUIZA": "MGLU3.SA",
        "JBSS3": "JBSS3.SA", "JBS": "JBSS3.SA",
        "LREN3": "LREN3.SA", "LOJAS RENNER": "LREN3.SA",
        "EGIE3": "EGIE3.SA", "ENGIE": "EGIE3.SA",
        "EQTL3": "EQTL3.SA", "EQUATORIAL": "EQTL3.SA",
        "TIMP3": "TIMP3.SA", "TIM": "TIMP3.SA",
        "VIVT3": "VIVT3.SA", "VIVO": "VIVT3.SA",
        "SANB3": "SANB3.SA", "SANTANDER": "SANB3.SA",
        "XPML3": "XPML3.SA", "XP": "XPML3.SA",
        "RAIL3": "RAIL3.SA", "RUMO": "RAIL3.SA",
        "CSNA3": "CSNA3.SA", "CSN": "CSNA3.SA",
        "GOAU3": "GOAU3.SA", "GERDAU": "GOAU3.SA",
        "GGBR4": "GGBR4.SA",
        "USIM5": "USIM5.SA", "USIMINAS": "USIM5.SA",
        "CMIG4": "CMIG4.SA", "CEMIG": "CMIG4.SA",
        "CPLE6": "CPLE6.SA", "COPEL": "CPLE6.SA",
        "ENBR3": "ENBR3.SA", "EDP": "ENBR3.SA",
        "CEEB3": "CEEB3.SA", "CEG": "CEEB3.SA",
    }

    try:
        # If specific symbol requested
        if symbol:
            yahoo_symbol = stock_map.get(symbol, f"{symbol}.SA")

            # Check if it's a portfolio (multiple stocks)
            if action == "portfolio" or "," in symbol:
                symbols = symbol.replace(" ", "").split(",")
                return _get_portfolio_prices(symbols, stock_map, player)

            return _get_single_stock_price(yahoo_symbol, symbol, player)

        # Return default portfolio
        return _get_portfolio_prices(default_stocks[:8], stock_map, player)

    except Exception as e:
        _log(f"Brazilian stocks error: {e}", player)
        webbrowser.open("https://www.google.com/finance/quote/PETR4:BVMF")
        return "Showing Brazilian stocks."

def _get_single_stock_price(yahoo_symbol: str, display_symbol: str, player=None) -> str:
    """Get price for a single Brazilian stock"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}?interval=1d&range=5d"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if "chart" in data and "result" in data["chart"] and data["chart"]["result"]:
                result = data["chart"]["result"][0]
                meta = result.get("meta", {})
                price = meta.get("regularMarketPrice")
                prev = meta.get("previousClose")
                currency = meta.get("currency", "BRL")

                if price and prev:
                    change = price - prev
                    pct = (change / prev) * 100
                    emoji = "📈" if change >= 0 else "📉"

                    # Get day's low/high
                    indicators = result.get("indicators", {})
                    quote = indicators.get("quote", [{}])[0]
                    low = min([l for l in quote.get("low", []) if l is not None]) if quote.get("low") else None
                    high = max([h for h in quote.get("high", []) if h is not None]) if quote.get("high") else None

                    result_str = f"🟢 {display_symbol} (B3)\n"
                    result_str += f"   Preço: R$ {price:.2f}\n"
                    result_str += f"   Variação: {emoji} {pct:+.2f}%\n"
                    result_str += f"   Anterior: R$ {prev:.2f}\n"
                    if low and high:
                        result_str += f"   Dia: R$ {low:.2f} - R$ {high:.2f}"

                    _log(result_str, player)
                    return result_str
                return f"{display_symbol}: Preço indisponível"
        return f"Ação não encontrada: {display_symbol}"
    except Exception as e:
        _log(f"Stock {display_symbol} error: {e}")
        return f"Erro ao buscar {display_symbol}"

def _get_portfolio_prices(symbols: list, stock_map: dict, player=None) -> str:
    """Get prices for multiple Brazilian stocks"""
    results = []

    for sym in symbols[:8]:
        yahoo_sym = stock_map.get(sym, f"{sym}.SA")
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_sym}?interval=1d&range=1d"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=5)

            if response.status_code == 200:
                data = response.json()
                if "chart" in data and "result" in data["chart"] and data["chart"]["result"]:
                    result = data["chart"]["result"][0]
                    meta = result.get("meta", {})
                    price = meta.get("regularMarketPrice")
                    prev = meta.get("previousClose")

                    if price and prev:
                        change = price - prev
                        pct = (change / prev) * 100
                        emoji = "📈" if change >= 0 else "📉"
                        results.append((sym, price, pct, emoji))
        except:
            pass

    if results:
        result = "📊 Carteira B3 (SP Capital):\n\n"
        for sym, price, pct, emoji in results:
            result += f"{emoji} {sym}: R$ {price:.2f} ({pct:+.2f}%)\n"

        # Calculate portfolio change
        total_pct = sum(pct for _, _, pct, _ in results) / len(results)
        result += f"\nMédia: {total_pct:+.2f}%"
        _log(result, player)
        return result

    return "Não foi possível carregar dados da bolsa."


def get_bovespa_index(parameters: dict, player=None) -> str:
    """Get Bovespa Index (Ibovespa) in real-time"""
    try:
        # Ibovespa via Yahoo Finance
        url = "https://query1.finance.yahoo.com/v8/finance/chart/^BVSP?interval=1d&range=5d"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if "chart" in data and "result" in data["chart"] and data["chart"]["result"]:
                result = data["chart"]["result"][0]
                meta = result.get("meta", {})
                price = meta.get("regularMarketPrice")
                prev = meta.get("previousClose")

                if price and prev:
                    change = price - prev
                    pct = (change / prev) * 100
                    emoji = "📈" if change >= 0 else "📉"

                    # Get intraday data for min/max
                    indicators = result.get("indicators", {})
                    quote = indicators.get("quote", [{}])[0]
                    lows = [l for l in quote.get("low", []) if l is not None]
                    highs = [h for h in quote.get("high", []) if h is not None]
                    day_low = min(lows) if lows else None
                    day_high = max(highs) if highs else None

                    result_str = f"📈 IBOVESPA\n"
                    result_str += f"   Pontos: {price:,.0f}\n"
                    result_str += f"   Variação: {emoji} {pct:+.2f}%\n"
                    result_str += f"   Anterior: {prev:,.0f}\n"
                    if day_low and day_high:
                        result_str += f"   Dia: {day_low:,.0f} - {day_high:,.0f}"

                    _log(result_str, player)
                    return result_str

        return "Ibovespa indisponível"
    except Exception as e:
        _log(f"Ibovespa error: {e}", player)
        return "Erro ao buscar Ibovespa"


def get_mini_contracts(parameters: dict, player=None) -> str:
    """Get Brazilian mini contracts (mini índice, mini dólar)"""
    try:
        # Mini Índice (WIN) - using proxy with future contract
        win_url = "https://query1.finance.yahoo.com/v8/finance/chart/WIN1.SA?interval=5m&range=1d"
        # Mini Dólar (WDO)
        wdo_url = "https://query1.finance.yahoo.com/v8/finance/chart/WDO1.SA?interval=5m&range=1d"

        headers = {"User-Agent": "Mozilla/5.0"}

        results = []

        # Try mini índice
        try:
            response = requests.get(win_url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if "chart" in data and "result" in data["chart"] and data["chart"]["result"]:
                    result = data["chart"]["result"][0]
                    meta = result.get("meta", {})
                    price = meta.get("regularMarketPrice")

                    if price:
                        # Get change from previous close
                        indicators = result.get("indicators", {})
                        quote = indicators.get("quote", [{}])[0]
                        opens = [o for o in quote.get("open", []) if o is not None]
                        if opens:
                            open_price = opens[0]
                            change = price - open_price
                            pct = (change / open_price) * 100 if open_price else 0
                            emoji = "📈" if change >= 0 else "📉"
                            results.append(("WIN", price, pct, emoji))
        except:
            pass

        # Try mini dólar
        try:
            response = requests.get(wdo_url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if "chart" in data and "result" in data["chart"] and data["chart"]["result"]:
                    result = data["chart"]["result"][0]
                    meta = result.get("meta", {})
                    price = meta.get("regularMarketPrice")

                    if price:
                        indicators = result.get("indicators", {})
                        quote = indicators.get("quote", [{}])[0]
                        opens = [o for o in quote.get("open", []) if o is not None]
                        if opens:
                            open_price = opens[0]
                            change = price - open_price
                            pct = (change / open_price) * 100 if open_price else 0
                            emoji = "📈" if change >= 0 else "📉"
                            results.append(("WDO", price, pct, emoji))
        except:
            pass

        if results:
            result = "📈 Mini Contratos (B3):\n\n"
            for sym, price, pct, emoji in results:
                if sym == "WIN":
                    result += f"📊 Mini Índice: {price:.0f} pts {emoji} ({pct:+.2f}%)\n"
                else:
                    result += f"💵 Mini Dólar: R$ {price:.2f} {emoji} ({pct:+.2f}%)\n"

            result += "\n🕐 Dados de mercado em tempo real"
            _log(result, player)
            return result

        # Fallback - try using direct BM&F data
        return _get_bmf_contracts_fallback(player)

    except Exception as e:
        _log(f"Mini contracts error: {e}", player)
        return _get_bmf_contracts_fallback(player)

def _get_bmf_contracts_fallback(player=None) -> str:
    """Fallback using alternative method for BM&F contracts"""
    try:
        # Try investing.com alternative via commodities
        url = "https://query1.finance.yahoo.com/v8/finance/chart/^DJI?interval=1d&range=1d"
        headers = {"User-Agent": "Mozilla/5.0"}

        # If all fails, provide a message about what user can ask
        return "Mini contratos: Use 'mini índice' ou 'mini dólar' para veros preços em tempo real.\n\nTente também: 'carteira', 'ibovespa', 'ação PETR4'."
    except:
        return "Dados dos mini contratos temporariamente indisponíveis."


def get_brazilian_market_news(parameters: dict, player=None) -> str:
    """Get Brazilian market news without browser"""
    topic = parameters.get("topic", "").lower()

    try:
        # Use GNews API for Brazilian financial news
        if topic:
            query = f"bolsa {topic} OR mercado financeiro {topic} OR ações {topic}"
        else:
            query = "bolsa brasileira OR mercado financeiro OR ibovespa OR b3"

        url = f"https://gnews.io/api/v4/search?q={quote_plus(query)}&lang=pt&max=5&apikey=demo"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            articles = data.get("articles", [])

            if articles:
                result = f"📰 Mercado Financeiro{' - ' + topic.title() if topic else ''}:\n\n"
                for i, article in enumerate(articles[:5], 1):
                    title = article.get("title", "")[:80]
                    source = article.get("source", {}).get("name", "")
                    result += f"{i}. {title}...\n   ({source})\n\n"
                _log(result, player)
                return result
        elif response.status_code == 401:
            return _get_brazil_news_fallback(topic, player)

        return _get_brazil_news_fallback(topic, player)

    except Exception as e:
        _log(f"Brazil news error: {e}", player)
        return _get_brazil_news_fallback(topic, player)

def _get_brazil_news_fallback(topic: str, player=None) -> str:
    """Fallback for Brazilian financial news using RSS"""
    try:
        if topic:
            rss_url = f"https://news.google.com/rss/search?q={quote_plus(topic + ' bolsa ações')}"
        else:
            rss_url = "https://news.google.com/rss/search?q=ibovespa+bolsa+brasil"

        feed = feedparser.parse(rss_url)
        if feed.entries:
            result = f"📰 Notícias Mercado{': ' + topic.title() if topic else ''}:\n\n"
            for i, entry in enumerate(feed.entries[:5], 1):
                title = entry.get("title", "")[:70]
                result += f"{i}. {title}...\n"
            result += "\n(Fonte: Google News)"
            return result
    except:
        pass

    webbrowser.open("https://www.google.com/search?q=noticias+bolsa+valores+brasil")
    return "Abrindo notícias do mercado financeiro."


def get_crypto_brl(parameters: dict, player=None) -> str:
    """Get cryptocurrency prices in Brazilian Real (BRL)"""
    coin = parameters.get("coin", "bitcoin").lower()

    try:
        # CoinGecko API - multiple currencies including BRL
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=brl,usd&include_24hr_change=true"
        headers = {"Accept": "application/json"}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if coin in data:
                brl_price = data[coin].get("brl")
                usd_price = data[coin].get("usd")
                change = data[coin].get("brl_24h_change", 0)

                if brl_price:
                    emoji = "📈" if change >= 0 else "📉"
                    result = f"₿ {coin.title()}\n"
                    result += f"   R$ {brl_price:,.2f} {emoji}\n"
                    result += f"   USD ${usd_price:,.2f}\n"
                    result += f"   24h: {change:+.2f}%"

                    _log(result, player)
                    return result
            return f"Criptomoeda não encontrada: {coin}"
        return f"Erro ao buscar {coin}"
    except Exception as e:
        _log(f"Crypto BRL error: {e}", player)
        webbrowser.open(f"https://www.coingecko.com/pt/precos")
        return "Abrindo preços de criptos."


# ========== BRAZILIAN REAL ESTATE MARKET ==========

# Major Brazilian construction/real estate companies on B3
CONSTRUCTION_STOCKS = {
    "CYRE3": "Cyrela",
    "EZTC3": "Eztec",
    "MRVE3": "MRV Engenharia",
    "GFSA3": "Gafisa",
    "TEND3": "Tenda",
    "DIRR3": "Direcional",
    "HBOR3": "Helbor",
    "PDGR3": "PDG Realty",
    "LOGG3": "Log Commercial",
    "ALPA3": "Aliansce",
    "BLAU3": "Blau Farmacêutica",  # Related to real estate investment
    "MPLU3": "Multiplan",
    "ALSO3": "Aliansce Shopping",
    "SMFT3": "Smartfit",  # Gym chain (real estate related)
    "VVEN3": "Viver",
    "EVEN3": "Even",
    "LWSA3": "Locus",
    "ROMI3": "Romi",
}

# SP Zones mapping
SP_ZONES = {
    "zona sul": ["zona-sul", "moema", "villa-mariana", "brooklin", "pinheiros", "itaim-bibi", "jardins", "moema", "campo-belo"],
    "zona norte": ["zona-norte", " Santana", "tucuruvi", "Casa Verde", "parada-de-lucas"],
    "zona leste": ["zona-leste", "tatuape", "mooca", "penha", "carrão", "itaquera"],
    "zona oeste": ["zona-oeste", "butanta", "pinheiros", "lapa", "perdizes", "pompeia"],
    "centro": ["centro", "centro-de-sp", "republica", "sé", "bela-vista"],
    "abcd": ["abc", "santo-andré", "são-bernardo", "são-caetano", "diadema", "ribeirao-pires"],
    "zona norte": ["zona-norte", "pari", "manicomi", "jaçanã", "jaraguá", "são-domingos"],
}


def get_real_estate_market(parameters: dict, player=None) -> str:
    """Get Brazilian real estate market data"""
    action = parameters.get("action", "").lower()
    zone = parameters.get("zone", "").lower()
    city = parameters.get("city", "sp").lower()
    developer = parameters.get("developer", "").lower()

    # If specific developer requested
    if developer:
        return _get_developer_data(developer, player)

    # If zone requested
    if zone:
        return _get_zone_data(zone, player)

    # Default - show top developers + market overview
    return _get_real_estate_overview(player)


def _get_real_estate_overview(player=None) -> str:
    """Get overview of Brazilian real estate market via construction stocks"""
    results = []

    # Map B3 stocks to Yahoo Finance format
    stock_map = {
        "CYRE3": "CYRE3.SA", "EZTC3": "EZTC3.SA", "MRVE3": "MRVE3.SA",
        "GFSA3": "GFSA3.SA", "TEND3": "TEND3.SA", "DIRR3": "DIRR3.SA",
        "HBOR3": "HBOR3.SA", "LOGG3": "LOGG3.SA", "MPLU3": "MPLU3.SA",
        "ALSO3": "ALSO3.SA", "EVEN3": "EVEN3.SA",
    }

    for sym, name in list(CONSTRUCTION_STOCKS.items())[:10]:
        yahoo_sym = stock_map.get(sym, f"{sym}.SA")
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_sym}?interval=1d&range=5d"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=5)

            if response.status_code == 200:
                data = response.json()
                if "chart" in data and "result" in data["chart"] and data["chart"]["result"]:
                    result = data["chart"]["result"][0]
                    meta = result.get("meta", {})
                    price = meta.get("regularMarketPrice")
                    prev = meta.get("previousClose")

                    if price and prev:
                        change = price - prev
                        pct = (change / prev) * 100
                        emoji = "📈" if change >= 0 else "📉"
                        results.append((name, sym, price, pct, emoji))
        except:
            pass

    if results:
        result = "🏗️ Construtoras - B3 (Top 10):\n\n"
        for name, sym, price, pct, emoji in results[:10]:
            result += f"{emoji} {name} ({sym}): R$ {price:.2f} ({pct:+.2f}%)\n"

        # Add market summary
        avg_change = sum(pct for _, _, _, pct, _ in results) / len(results)
        result += f"\n📊 Variação média do setor: {avg_change:+.2f}%\n"

        # Add explanation
        result += "\n💡 Para dados por zona de SP, peça: 'imóveis zona sul' ou 'imóveis abc'\n"
        result += "   Para uma construtora específica: 'construtora Cyrela'"

        _log(result, player)
        return result

    return _get_real_estate_fallback(player)


def _get_developer_data(developer: str, player=None) -> str:
    """Get data for a specific developer/construction company"""

    # Find matching developer
    dev_map = {}
    for sym, name in CONSTRUCTION_STOCKS.items():
        name_lower = name.lower()
        dev_map[name_lower] = (sym, name)
        dev_map[sym.lower()] = (sym, name)

    # Try to find match
    match = None
    for key, val in dev_map.items():
        if developer in key or key in developer:
            match = val
            break

    if not match:
        return f"Construtora não encontrada: {developer}. Tente: Cyrela, MRV, Eztec, Gafisa, Tenda, Direcional."

    sym, name = match
    yahoo_sym = f"{sym}.SA"

    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_sym}?interval=1d&range=30d"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if "chart" in data and "result" in data["chart"] and data["chart"]["result"]:
                result = data["chart"]["result"][0]
                meta = result.get("meta", {})
                price = meta.get("regularMarketPrice")
                prev = meta.get("previousClose")
                avg_volume = meta.get("averageVolume", 0)

                if price and prev:
                    change = price - prev
                    pct = (change / prev) * 100
                    emoji = "📈" if change >= 0 else "📉"

                    result_str = f"🏢 {name} ({sym})\n"
                    result_str += f"   Cotação: R$ {price:.2f}\n"
                    result_str += f"   Variação: {emoji} {pct:+.2f}%\n"
                    result_str += f"   Volume médio: {avg_volume:,} ações/dia\n"

                    # Get 30-day range
                    indicators = result.get("indicators", {})
                    quote = indicators.get("quote", [{}])[0]
                    lows = [l for l in quote.get("low", []) if l is not None]
                    highs = [h for h in quote.get("high", []) if h is not None]

                    if lows and highs:
                        min_30d = min(lows)
                        max_30d = max(highs)
                        result_str += f"   30 dias: R$ {min_30d:.2f} - R$ {max_30d:.2f}"

                    _log(result_str, player)
                    return result_str

        return f"Dados indisponíveis para {name}"
    except Exception as e:
        _log(f"Developer {developer} error: {e}", player)
        return f"Erro ao buscar dados de {name}"


def _get_zone_data(zone: str, player=None) -> str:
    """Get real estate data for specific SP zone"""

    # Since there's no free public API for zone-specific sales data,
    # we provide what we can and suggest alternatives

    zone_info = {
        "zona sul": {
            "bairros": "Moema, Vila Mariana, Brooklin, Pinheiros, Itaim Bibi, Jardins",
            "preco_medio": "R$ 8.000 - R$ 15.000/m²",
            "demanda": "Alta",
            " principals": "Cyrela, Eztec, Mourao"
        },
        "zona norte": {
            "bairros": "Santana, Tucuruvi, Casa Verde, Jaçanã",
            "preco_medio": "R$ 4.500 - R$ 7.000/m²",
            "demanda": "Média",
            "principais": "MRV, Tenda, Direcional"
        },
        "zona leste": {
            "bairros": "Tatuapé, Mooca, Penha, Carrão, Itaquera",
            "preco_medio": "R$ 5.000 - R$ 8.000/m²",
            "demanda": "Alta",
            "principais": "MRV, Cyrela, Gafisa"
        },
        "zona oeste": {
            "bairros": "Butantã, Pinheiros, Lapa, Perdizes, Pompeia",
            "preco_medio": "R$ 7.000 - R$ 12.000/m²",
            "demanda": "Alta",
            "principais": "Eztec, Even, Cyrela"
        },
        "centro": {
            "bairros": "República, Sé, Bela Vista, Bom Retiro",
            "preco_medio": "R$ 8.000 - R$ 18.000/m²",
            "demanda": "Média-Alta",
            "principais": "Construtoras pequenas, incorporadoras locais"
        },
        "abcd": {
            "bairros": "Santo André, São Bernardo, São Caetano, Diadema",
            "preco_medio": "R$ 5.500 - R$ 9.000/m²",
            "demanda": "Alta",
            "principais": "MRV, Tenda, Cyrela, Gafisa"
        },
    }

    if zone in zone_info:
        info = zone_info[zone]
        result = f"🏘️ Imóveis - {zone.upper()}\n\n"
        result += f"📍 Principais bairros:\n   {info['bairros']}\n\n"
        result += f"💰 Preço médio por m²:\n   {info['preco_medio']}\n\n"
        result += f"📈 Demanda:\n   {info['demanda']}\n\n"
        result += f"🏗️ Principais construtoras:\n   {info['principais']}\n\n"
        result += "⚠️ *Dados baseados em médias de mercado. Para dados atualizados,\n"
        result += "   recomendo consultar: Zap, VivaReal, ImóvelWeb ou Secovi-SP."

        _log(result, player)
        return result

    # Try partial match
    for z, info in zone_info.items():
        if zone in z or z in zone:
            return _get_zone_data(z, player)

    return "Zona não reconhecida. Tente: zona sul, zona norte, zona leste, zona oeste, centro ou abcd."


def _get_real_estate_fallback(player=None) -> str:
    """Fallback message with real estate market info"""
    result = "🏘️ Mercado Imobiliário - SP\n\n"
    result += "📊 Principais Construtoras na B3:\n"
    result += "   • Cyrela (CYRE3)\n"
    result += "   • Eztec (EZTC3)\n"
    result += "   • MRV Engenharia (MRVE3)\n"
    result += "   • Gafisa (GFSA3)\n"
    result += "   • Tenda (TEND3)\n"
    result += "   • Direcional (DIRR3)\n\n"
    result += "📍 Por zona de SP:\n"
    result += "   Zona Sul: R$ 8.000-15.000/m²\n"
    result += "   Zona Oeste: R$ 7.000-12.000/m²\n"
    result += "   Zona Leste: R$ 5.000-8.000/m²\n"
    result += "   Zona Norte: R$ 4.500-7.000/m²\n"
    result += "   ABCD: R$ 5.500-9.000/m²\n\n"
    result += "💡 Peça: 'imóveis zona sul', 'construtora Cyrela' ou 'carteira'\n"

    _log(result, player)
    return result


def get_real_estate_news(parameters: dict, player=None) -> str:
    """Get real estate news from Brazil"""
    topic = parameters.get("topic", "").lower()

    try:
        # Use GNews API for Brazilian real estate news
        if topic:
            query = f"imobiliário {topic} OR mercado imobiliário {topic}"
        else:
            query = "mercado imobiliário OR imóveis OR construtoras OR venda apartamentos"

        url = f"https://gnews.io/api/v4/search?q={quote_plus(query)}&lang=pt&max=5&apikey=demo"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            articles = data.get("articles", [])

            if articles:
                result = f"🏘️ Imobiliário{': ' + topic.title() if topic else ''}:\n\n"
                for i, article in enumerate(articles[:5], 1):
                    title = article.get("title", "")[:80]
                    source = article.get("source", {}).get("name", "")
                    result += f"{i}. {title}...\n   ({source})\n\n"
                _log(result, player)
                return result

        return get_real_estate_news_fallback(topic, player)

    except Exception as e:
        _log(f"Real estate news error: {e}", player)
        return get_real_estate_news_fallback(topic, player)


def get_real_estate_news_fallback(topic: str, player=None) -> str:
    """Fallback for real estate news"""
    try:
        rss_url = f"https://news.google.com/rss/search?q={quote_plus('imobiliário mercado imóveis')}"
        feed = feedparser.parse(rss_url)
        if feed.entries:
            result = "🏘️ Notícias Imobiliárias:\n\n"
            for i, entry in enumerate(feed.entries[:5], 1):
                title = entry.get("title", "")[:70]
                result += f"{i}. {title}...\n"
            return result
    except:
        pass

    webbrowser.open("https://www.google.com/search?q=mercado+imobiliario+sp+vendas+construtoras")
    return "Abrindo notícias do mercado imobiliário."


def get_financing_data(parameters: dict, player=None) -> str:
    """Get financing data from Caixa (government bank) - approximate data"""

    # Since direct API is not available, provide approximate data based on market reports
    result = "💰 Financiamento Imobiliário - SP (Estimativas)\n\n"
    result += "📊 Taxas médias (Caixa / Bancos):\n"
    result += "   • SFH (até R$ 1,5M): a partir de 8,5% a.a.\n"
    result += "   • SCI (R$ 1,5M - 3M): a partir de 9,5% a.a.\n"
    result += "   • Comercial: a partir de 10% a.a.\n\n"
    result += "📈 Mercado 2024-2025:\n"
    result += "   • Volume de financiamento em alta\n"
    result += "   • Construtoras com lançamentosrecordes\n"
    result += "   • Demanda aquecida na Grande SP\n\n"
    result += "🏆 Maiores financiadoras:\n"
    result += "   1. Caixa Econômica Federal\n"
    result += "   2. Banco do Brasil\n"
    result += "   3. Itaú\n"
    result += "   4. Bradesco\n"
    result += "   5. Santander\n\n"
    result += "⚠️ *Dados aproximados. Para valores exatos,\n"
    result += "   consulte diretamente os bancos ou USE a ferramenta.\n"
    result += "   Digite 'simular financiamento 300000' para ajuda."

    _log(result, player)
    return result


def info_service(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """Main info service handler"""
    params = parameters or {}
    info_type = params.get("type", "").lower()
    action = params.get("action", "").lower()

    _log(f"Info service: type={info_type}, action={action}, params={params}", player)

    # Route to appropriate function
    if info_type in ["crypto", "cryptocurrency", "bitcoin", "btc", "ethereum", "eth"]:
        return get_crypto_price(params, player)
    elif info_type in ["crypto_brl", "cripto", "bitcoin_brl"]:
        return get_crypto_brl(params, player)
    elif info_type in ["stock", "stock_price", "acao", "bovespa", "b3", "bolsa"]:
        return get_brazilian_stocks(params, player)
    elif info_type in ["ibovespa", "indice", "index"]:
        return get_bovespa_index(params, player)
    elif info_type in ["mini", "mini_contracts", "mini_indice", "mini_dolar", "win", "wdo"]:
        return get_mini_contracts(params, player)
    elif info_type in ["market_news", "noticias_mercado", "noticias_financeiras"]:
        return get_brazilian_market_news(params, player)
    elif info_type in ["weather", "clima", "previsao"]:
        return get_weather(params, player)
    elif info_type in ["news", "noticias", "newspaper"]:
        return get_news(params, player)
    elif info_type in ["sports", "esportes", "score", "scores"]:
        return get_sports_score(params, player)
    elif info_type in ["currency", "exchange", "moeda", "cambio"]:
        return get_currency_exchange(params, player)
    elif info_type in ["define", "definition", "dicionario"]:
        return get_definition(params, player)
    elif info_type in ["trivia", "quiz"]:
        return get_trivia(params, player)
    elif info_type in ["fact", "random_fact"]:
        return get_fact(params, player)
    elif info_type in ["population", "populacao"]:
        return get_population(params, player)
    elif info_type in ["real_estate", "imoveis", "imobiliario", "construtora", "construtoras"]:
        return get_real_estate_market(params, player)
    elif info_type in ["real_estate_news", "noticias_imoveis", "noticias_imobiliarias"]:
        return get_real_estate_news(params, player)
    elif info_type in ["financing", "financiamento", "credito_imobiliario"]:
        return get_financing_data(params, player)
    else:
        return "Unknown info type. Try: crypto, stock, weather, news, sports, currency, definition, trivia, fact, population, ibovespa, mini, market_news, crypto_brl, real_estate, financing, ou real_estate_news."