import websocket, config, json, talib, time, datetime, re
import pandas as pd
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceOrderException

#Key in usdt pair to trade and time frame
#========================================
symbol = 'thetausdt'
tframe = '1m'
#========================================

if tframe[-1] == 'm':
    tf1 = int(re.findall('\d+', tframe)[0])
    tme_frame = 1 * tf1
if tframe[-1] == 'h':
    tf1 = int(re.findall('\d+', tframe)[0])
    tme_frame = 60 * tf1

futures_websocket = 'wss://fstream3.binance.com/ws/{}@kline_{}'.format(symbol, tframe)

client = Client(config.API_KEY, config.API_SECRET)

TRADE_SYMBOL = '{}'.format(symbol.upper())

#WARNING: Always check the settings below before running the bot
#===================================================================
Lev = 5 #leverage settings
rrr = 2 #risk reward ratio
risk = 0.025 #risk percent drop from initial balance stops the bot
risk_usd = 0.5 #risk per trade

#stop loss settings
stop_csticks = 10 #count n candlesticks backward for stop loss
stop_range = 1

#EMA and MACD default settings: 200, 12, 26, 9 respectively
slowest_EMA = 200
macd_fast = 12
macd_slow = 26
macd_signal = 9
atr_period = 14
#===================================================================
in_pos = []
ep_list = []
sl_list = []
tp_list = []
qty_list = []
sl_id_list = []
tp_id_list = []
last_side = []
new_sl = []

#get number of decimals of the selected coin
data = client.futures_exchange_info()

symbol_list = []
precision = []

for pair in data['symbols']:
    if pair['status'] == 'TRADING':
        symbol_list.append(pair['symbol'])
        precision.append(pair['pricePrecision'])

df2 = pd.DataFrame(symbol_list)
df1 = pd.DataFrame(precision)
merge = pd.concat([df1, df2], axis=1)
merge.columns = ['precision', 'symbol']
merge.set_index('precision', inplace=True)
symbol_loc = merge.index[merge.symbol == TRADE_SYMBOL]
round_off = symbol_loc[-1]

#logging initial balance
start_balance = client.futures_account_balance()
initial_balance = start_balance[0]['balance']
print("================================")
print('Initial balance:  {}'.format(initial_balance))
print("================================")
with open("initial_balance.txt", "a+") as file_object:
    file_object.seek(0)
    data = file_object.read(100)
    if len(data) > 0:
        file_object.write("\n")
    file_object.write(initial_balance)

time.sleep(1)

#setting leverage
change_leverage = client.futures_change_leverage(symbol=TRADE_SYMBOL, leverage=Lev)
print('Leverage set to: ', change_leverage['leverage'])

time.sleep(1)

#get historical data
csticks = client.futures_klines(symbol=TRADE_SYMBOL, interval=tframe)
df = pd.DataFrame(csticks)
df_edited = df.drop([0,6,7,8,9,10,11], axis=1)
df_final = df_edited.drop(df_edited.tail(1).index)
df_final.columns = ['o', 'h', 'l', 'c', 'v']
df_final['slowest_EMA'] = round(talib.EMA(df_final['c'], slowest_EMA), round_off)
df_final['macd'], df_final['macdSignal'], df_final['macdHist'] = talib.MACD(df_final['c'], fastperiod=macd_fast, slowperiod=macd_slow, signalperiod=macd_signal)
df_final['ATR'] = talib.ATR(df_final['h'], df_final['l'], df_final['c'], timeperiod=atr_period)
df_final['RSI'] = round(talib.RSI(df_final['c'], atr_period), 2)
print(df_final)

def on_open(ws):
    print('Receiving Data...')

def on_close(ws):
    print('Connection Closed')

def on_message(ws, message):
    global df_final, in_pos, ep_list, sl_list, tp_list, qty_list, sl_id_list, tp_id_list, last_side, new_sl

    json_message = json.loads(message)
    candle = json_message['k']
    candle_closed = candle['x']
    open_data = candle['o']
    high_data = candle['h']
    low_data = candle['l']
    close_data = candle['c']

    if candle_closed:
        df_final = df_final.append(candle, ignore_index=True)
        df_final['slowest_EMA'] = round(talib.EMA(df_final['c'], slowest_EMA), round_off)
        df_final['macd'], df_final['macdSignal'], df_final['macdHist'] = talib.MACD(df_final['c'], fastperiod=macd_fast, slowperiod=macd_slow, signalperiod=macd_signal)
        df_final['ATR'] = talib.ATR(df_final['h'], df_final['l'], df_final['c'], timeperiod=atr_period)
        df_final['RSI'] = round(talib.RSI(df_final['c'], atr_period), 2)

        last_open = df_final['o'].tail(1)
        last_high = df_final['h'].tail(1)
        last_low = df_final['l'].tail(1)
        last_close = df_final['c'].tail(1)
        last_slowest_EMA = df_final['slowest_EMA'].tail(1)
        last_macd = round(df_final['macd'].tail(1), round_off + 2)
        last_macdSignal = round(df_final['macdSignal'].tail(1), round_off + 2)
        last_ATR = round(df_final['ATR'].tail(1), round_off)
        last_RSI = round(df_final['RSI'].tail(1), 2)
        rsi_2c_ago = round(df_final['RSI'].iloc[-2], 2)
        macd_3c_ago = round(df_final['macd'].iloc[-3], round_off + 2)
        macdSignal_3c_ago = round(df_final['macdSignal'].iloc[-3], round_off + 2)
        macd_2c_ago = round(df_final['macd'].iloc[-2], round_off + 2)

        print('==================================================================')
        now = datetime.datetime.now()
        print('Current time is: {}'.format(now.strftime("%d/%m/%Y %H:%M:%S")))
        print('==================================================================')

        print("Open: {}".format(open_data), "  |  " "High: {}".format(high_data), "  |  " "Low: {}".format(low_data), "  |  " "Close: {}".format(close_data))
        print('Slowest EMA: {}'.format(float(df_final['slowest_EMA'].tail(1))))
        print('MACD: {:f}'.format(float(last_macd)))
        print('MACD Signal: {:f}'.format(float(last_macdSignal)))
        print('ATR: {}'.format(float(last_ATR)))
        print('RSI: {}'.format(float(last_RSI)))

        def isin():
            if len(in_pos) != 0:
                in_position = True
            else:
                in_position = False
            return in_position

        def set_new_sl():
            if len(new_sl) != 0:
                new_stop = True
            else:
                new_stop = False
            return new_stop

        if isin():
            print('################')
            print('IN AN OPEN TRADE')
            print('################')

            sl_status = client.futures_get_order(symbol=TRADE_SYMBOL, orderId=sl_id_list[-1])['status']
            if sl_status == 'FILLED':
                print('################')
                print('STOP LOSS FILLED')
                print('################')
                cancel_tp = client.futures_cancel_order(symbol=TRADE_SYMBOL, orderId=tp_id_list[-1])
                in_pos.pop(), ep_list.pop(), sl_list.pop(), tp_list.pop(), qty_list.pop(), sl_id_list.pop(), tp_id_list.pop(), last_side.pop()
                if len(new_sl) != 0:
                    new_sl.pop()
            
            time.sleep(1)

            tp_status = client.futures_get_order(symbol=TRADE_SYMBOL, orderId=tp_id_list[-1])['status']
            if tp_status == 'FILLED':
                print('##################')
                print('TAKE PROFIT FILLED')
                print('##################')
                cancel_sl = client.futures_cancel_order(symbol=TRADE_SYMBOL, orderId=sl_id_list[-1])
                in_pos.pop(), ep_list.pop(), sl_list.pop(), tp_list.pop(), qty_list.pop(), sl_id_list.pop(), tp_id_list.pop(), last_side.pop()
                if len(new_sl) != 0:
                    new_sl.pop()

            if not set_new_sl():
                if last_side[-1] == 'BUY':
                    stop_loss_adjust = round(float(ep_list[-1]) + ((float(ep_list[-1]) * 1.001) - float(ep_list[-1])), round_off)
                    break_even = (float(ep_list[-1]) + (float(ep_list[-1]) - float(sl_list[-1])))
                    if float(last_high) >= float(break_even):
                        print('Stop loss adjusted to break even')
                        cancel_order = client.futures_cancel_order(symbol=TRADE_SYMBOL, orderId=sl_id_list[-1])
                        sl_id_list.pop(), sl_list.pop()
                        time.sleep(1)
                        create_new_sl = client.futures_create_order(symbol=TRADE_SYMBOL, side='SELL', type='STOP_MARKET', quantity=qty_list[-1], stopPrice=stop_loss_adjust)
                        sl_id = create_new_sl['orderId']
                        sl_id_list.append(sl_id)
                        sl_list.append(stop_loss_adjust)
                        new_sl.append('YES')

                elif last_side[-1] == 'SELL':
                    stop_loss_adjust = round(float(ep_list[-1]) - ((float(ep_list[-1]) * 1.001) - float(ep_list[-1])), round_off)
                    break_even = (float(ep_list[-1]) - (float(sl_list[-1]) - float(ep_list[-1])))
                    if float(last_low) <= float(break_even):
                        print('Stop loss adjusted to break even')
                        cancel_order = client.futures_cancel_order(symbol=TRADE_SYMBOL, orderId=sl_id_list[-1])
                        sl_id_list.pop(), sl_list.pop()
                        time.sleep(1)
                        create_new_sl = client.futures_create_order(symbol=TRADE_SYMBOL, side='BUY', type='STOP_MARKET', quantity=qty_list[-1], stopPrice=stop_loss_adjust)
                        sl_id = create_new_sl['orderId']
                        sl_id_list.append(sl_id)
                        sl_list.append(stop_loss_adjust)
                        new_sl.append('YES')
    
        highest = max(df_final['h'].tail(stop_csticks)) 
        lowest = min(df_final['l'].tail(stop_csticks))
        SL_range_buy = ((float(last_low) / float(lowest)) - 1) * 100
        SL_range_sell = ((float(highest) / float(last_high)) - 1) * 100

        #Buy Condition
        if float(macd_3c_ago) < float(macdSignal_3c_ago) and float(last_macd) > float(last_macdSignal) and float(macd_2c_ago) < 0 and float(last_close) > float(last_slowest_EMA) and float(rsi_2c_ago) > 40 and float(last_RSI) < 60 and SL_range_buy <= stop_range:
            # print('##################')
            # print('BUY SIGNAL IS ON!')
            # print('##################')

            #condition 1: check if current balance is still above your risk
            now_balance = client.futures_account_balance()
            current_balance = now_balance[0]['balance']
            with open("current_balance.txt", "a+") as file_object:
                file_object.seek(0)
                data = file_object.read(100)
                if len(data) > 0:
                    file_object.write("\n")
                file_object.write(current_balance)
            with open('initial_balance.txt', 'r') as f:
                lines = f.read().splitlines()
                initial = float(lines[-1])
            with open('current_balance.txt', 'r') as f:
                lines = f.read().splitlines()
                current = float(lines[-1])
                
                if (initial - (initial * risk)) > current:
                    time.sleep(2)
                    sys.exit('Today is not your day. Bot is terminating.')

            time.sleep(1)
        
            #if not in position will proceed to buy
            if not isin():
                print('#################################')
                print('BUY SIGNAL IS ON! Executing order')
                print('#################################')
                print("=========================================================")
                entry_price1 = float(last_close)
                entry_price = (round(entry_price1, round_off))
                print("Entry Price at: {}".format(entry_price))

                min_val = min(df_final['l'].tail(stop_csticks))
                sl = float(min_val) - float(last_ATR)
                stop_loss = (round(sl, round_off))
                print("Calculated stop loss at: {}".format(stop_loss))

                tp = (rrr * (entry_price - stop_loss)) + entry_price
                take_profit = (round(tp, round_off))
                print("Calculated take profit at: {}".format(take_profit))
                    
                SL_range = ((entry_price / stop_loss) - 1) * Lev
                capital = risk_usd / SL_range

                trade_quant = (capital * Lev) / entry_price
                TRADE_QUANTITY = (round(trade_quant))
                print("Trade Quantity: {}".format(TRADE_QUANTITY))
                print("=========================================================")

                try:
                    buy_limit_order = client.futures_create_order(symbol=TRADE_SYMBOL, side='BUY', type='LIMIT', timeInForce='GTC', price=entry_price, quantity=TRADE_QUANTITY)
                    order_id = buy_limit_order['orderId']
                    order_status = buy_limit_order['status']

                    timeout = time.time() + (50 * tme_frame)
                    while order_status != 'FILLED':
                        time.sleep(10)
                        order_status = client.futures_get_order(symbol=TRADE_SYMBOL, orderId=order_id)['status']
                        print(order_status)

                        if order_status == 'FILLED':
                            in_pos.append('YES')
                            last_side.append('BUY')
                            ep_list.append(entry_price)
                            qty_list.append(TRADE_QUANTITY)

                            time.sleep(1)
                            set_stop_loss = client.futures_create_order(symbol=TRADE_SYMBOL, side='SELL', type='STOP_MARKET', quantity=TRADE_QUANTITY, stopPrice=stop_loss)
                            sl_id = set_stop_loss['orderId']
                            sl_id_list.append(sl_id)
                            sl_list.append(stop_loss)
                            time.sleep(1)
                            set_take_profit = client.futures_create_order(symbol=TRADE_SYMBOL, side='SELL', type='TAKE_PROFIT_MARKET', quantity=TRADE_QUANTITY, stopPrice=take_profit)
                            tp_id = set_take_profit['orderId']
                            tp_id_list.append(tp_id)
                            tp_list.append(take_profit)
                            break

                        if time.time() > timeout:
                            check_order = client.futures_get_order(symbol=TRADE_SYMBOL, orderId=order_id)
                            order_status = check_order['status']
                            partial_qty = check_order['executedQty']
                            print(partial_qty)
                            
                            if order_status == 'PARTIALLY_FILLED':
                                cancel_order = client.futures_cancel_order(symbol=TRADE_SYMBOL, orderId=order_id)
                                in_pos.append('YES')
                                last_side.append('BUY')
                                ep_list.append(entry_price)
                                qty_list.append(partial_qty)

                                time.sleep(1)
                                set_stop_loss = client.futures_create_order(symbol=TRADE_SYMBOL, side='SELL', type='STOP_MARKET', quantity=qty_list[-1], stopPrice=stop_loss)
                                sl_id = set_stop_loss['orderId']
                                sl_id_list.append(sl_id)
                                sl_list.append(stop_loss)
                                time.sleep(1)
                                set_take_profit = client.futures_create_order(symbol=TRADE_SYMBOL, side='SELL', type='TAKE_PROFIT_MARKET', quantity=qty_list[-1], stopPrice=take_profit)
                                tp_id = set_take_profit['orderId']
                                tp_id_list.append(tp_id)
                                tp_list.append(take_profit)
                                break
                            
                            else:
                                cancel_order = client.futures_cancel_order(symbol=TRADE_SYMBOL, orderId=order_id)
                                break
                        
                except BinanceAPIException as e:
                    # error handling goes here
                    print(e)
                except BinanceOrderException as e:
                    # error handling goes here
                    print(e)
            else:
                print("Buy long signal is on but you are already in position..")
    
        #Sell Condition
        if float(macd_3c_ago) > float(macdSignal_3c_ago) and float(last_macd) < float(last_macdSignal) and float(macd_2c_ago) > 0 and float(last_close) < float(last_slowest_EMA) and float(rsi_2c_ago) < 60 and float(last_RSI) > 40 and SL_range_sell <= stop_range:
            # print('##################')
            # print('SELL SIGNAL IS ON!')
            # print('##################')

            #condition 1: check if current balance is still above your risk
            now_balance = client.futures_account_balance()
            current_balance = now_balance[0]['balance']
            with open("current_balance.txt", "a+") as file_object:
                file_object.seek(0)
                data = file_object.read(100)
                if len(data) > 0:
                    file_object.write("\n")
                file_object.write(current_balance)
            with open('initial_balance.txt', 'r') as f:
                lines = f.read().splitlines()
                initial = float(lines[-1])
            with open('current_balance.txt', 'r') as f:
                lines = f.read().splitlines()
                current = float(lines[-1])
                
                if (initial - (initial * risk)) > current:
                    time.sleep(2)
                    sys.exit('Today is not your day. Bot is terminating.')
                
            time.sleep(1)
                
            if not isin():
                print('##################################')
                print('SELL SIGNAL IS ON! Executing order')
                print('##################################')
                print("=========================================================")
                entry_price1 = float(last_close)
                entry_price = (round(entry_price1, round_off))
                print("Entry Price at: {}".format(entry_price))

                max_val = max(df_final['h'].tail(stop_csticks))
                sl = float(max_val) + float(last_ATR)
                stop_loss = (round(sl, round_off))
                print("Calculated stop loss at: {}".format(stop_loss))

                tp = (entry_price - (rrr * (stop_loss - entry_price)))
                take_profit = (round(tp, round_off))
                print("Calculated take profit at: {}".format(take_profit))

                SL_range = ((stop_loss / entry_price) - 1) * Lev
                capital = risk_usd / SL_range

                trade_quant = (capital * Lev) / entry_price
                TRADE_QUANTITY = (round(trade_quant))
                print("Trade Quantity: {}".format(TRADE_QUANTITY))
                print("=========================================================")

                try:
                    sell_limit_order = client.futures_create_order(symbol=TRADE_SYMBOL, side='SELL', type='LIMIT', timeInForce='GTC', price=entry_price, quantity=TRADE_QUANTITY)
                    order_id = sell_limit_order['orderId']
                    order_status = sell_limit_order['status']

                    timeout = time.time() + (50 * tme_frame)
                    while order_status != 'FILLED':
                        time.sleep(10) #check every 10sec if limit order has been filled
                        order_status = client.futures_get_order(symbol=TRADE_SYMBOL, orderId=order_id)['status']
                        print(order_status)

                        if order_status == 'FILLED':
                            in_pos.append('YES')
                            last_side.append('SELL')
                            ep_list.append(entry_price)
                            qty_list.append(TRADE_QUANTITY)

                            time.sleep(1)
                            set_stop_loss = client.futures_create_order(symbol=TRADE_SYMBOL, side='BUY', type='STOP_MARKET', quantity=TRADE_QUANTITY, stopPrice=stop_loss)
                            sl_id = set_stop_loss['orderId']
                            sl_id_list.append(sl_id)
                            sl_list.append(stop_loss)
                            time.sleep(1)
                            set_take_profit = client.futures_create_order(symbol=TRADE_SYMBOL, side='BUY', type='TAKE_PROFIT_MARKET', quantity=TRADE_QUANTITY, stopPrice=take_profit)
                            tp_id = set_take_profit['orderId']
                            tp_id_list.append(tp_id)
                            tp_list.append(take_profit)
                            break

                        if time.time() > timeout:
                            check_order = client.futures_get_order(symbol=TRADE_SYMBOL, orderId=order_id)
                            order_status = check_order['status']
                            partial_qty = check_order['executedQty']
                            print(partial_qty)
                            
                            if order_status == 'PARTIALLY_FILLED':
                                cancel_order = client.futures_cancel_order(symbol=TRADE_SYMBOL, orderId=order_id)
                                in_pos.append('YES')
                                last_side.append('SELL')
                                ep_list.append(entry_price)
                                qty_list.append(partial_qty)

                                time.sleep(1)
                                set_stop_loss = client.futures_create_order(symbol=TRADE_SYMBOL, side='BUY', type='STOP_MARKET', quantity=qty_list[-1], stopPrice=stop_loss)
                                sl_id = set_stop_loss['orderId']
                                sl_id_list.append(sl_id)
                                sl_list.append(stop_loss)
                                time.sleep(1)
                                set_take_profit = client.futures_create_order(symbol=TRADE_SYMBOL, side='BUY', type='TAKE_PROFIT_MARKET', quantity=qty_list[-1], stopPrice=take_profit)
                                tp_id = set_take_profit['orderId']
                                tp_id_list.append(tp_id)
                                tp_list.append(take_profit)
                                break
                            
                            else:
                                cancel_order = client.futures_cancel_order(symbol=TRADE_SYMBOL, orderId=order_id)
                                break

                except BinanceAPIException as e:
                    # error handling goes here
                    print(e)
                except BinanceOrderException as e:
                    # error handling goes here
                    print(e)

            else:
                print("Sell short signal is on but you are already in position..")

ws = websocket.WebSocketApp(futures_websocket, on_open=on_open, on_close=on_close, on_message=on_message)
ws.run_forever()
