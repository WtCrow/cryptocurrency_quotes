var chart = Highcharts.stockChart('ohlc_chart', {
    title: {text: 'Select pair'},
    rangeSelector: {enabled:false},
    yAxis: [{
            labels: {
                align: 'right',
                x: -3
            },
            title: {
                text: 'OHLC'
            },
            height: '60%',
            lineWidth: 2
        },
        {
            labels: {
                align: 'right',
                x: -3
            },
            title: {
                text: 'Volume'
            },
            top: '65%',
            height: '35%',
            offset: 0,
            lineWidth: 2
        }],

    tooltip: {
        split: true
    },

    series: [{
            type: 'candlestick',
            name: 'candles'
        },
        {
            type: 'column',
            name: 'volumes',
            yAxis: 1
        }]
});
// Data series
var ohlc = [],
    vol = [];

// Variable for CSS-selected
var selectedPair = '';
var selectedRow = null;

// Current selected exchange
var exchange = '';

var chartPair = '',
    chartExchange = '',
    timeFrame = '';

// Need for check data from ws - this new or old candle
var lastTime = 0;

// Format: {exchange:[[time_frames],[pairs]], ...}
var listing = null;

// data_id send in format: msg_type.data_type.exchange.pair[.time_frame] or listing_info
var MSG_TYPE_START = 'starting',
    MSG_TYPE_UPD = 'update';
var DATA_TYPE_LISTING = 'listing_info',
    DATA_TYPE_TICKER = 'ticker',
    DATA_TYPE_CANDLES = 'candles',
    DATA_TYPE_DEPTH = 'depth';
var ACTION_SUB = 'sub',
    ACTION_UNSUB = 'unsub'

var wsUri = (window.location.protocol == 'https:' && 'wss://' || 'ws://') + window.location.host + '/api/v1/ws';
var conn = new WebSocket(wsUri);
conn.onmessage = function(e) {
    var message = JSON.parse(e.data);

    // if send error, msg contain error key
    if (message.hasOwnProperty('error')) {
        errorMsg(message['data_id'], message['error']);
        return
    }

    if (message['data_id'] == DATA_TYPE_LISTING) {
        // message with listing contain JSON
        updateListing(JSON.parse(message['data']))
        return
    }

    // format: msg_type.data_type.exchange.pair[.time_frame]
    fragment_id = message['data_id'].split('.');
    switch (fragment_id[1]) {
        case DATA_TYPE_TICKER: {
            exchange_and_pair = fragment_id[2] + ' | ' + fragment_id[3]
            updateTicker(exchange_and_pair, message['data'])
            break;
        }
        case DATA_TYPE_CANDLES: {
            // if chart data change, but ws send update
            if (chartExchange != fragment_id[2] || chartPair != fragment_id[3] || timeFrame != fragment_id[4]) { return; }
            // if server send empty message return
            if (message['data'].length == 0) { return; }

            if (fragment_id[0] == MSG_TYPE_START) {
                setCandles(message['data'])
                chart.setTitle({text: fragment_id[2] + ' | ' + fragment_id[3]});
            }
            else {
                if (fragment_id[0] == MSG_TYPE_UPD) {
                    updateCandle(message['data'])
                }
            }
            break;
        }
        case DATA_TYPE_DEPTH: {
            // if chart data change, but ws send update
            if (chartExchange != fragment_id[2] || chartPair != fragment_id[3]) { return; }
            updateDepth(message['data'])
            break;
        }
    }
};
conn.onopen = function() {
    // first action - get listing information
    sendRequest(ACTION_SUB, DATA_TYPE_LISTING);
};
conn.onclose = function() {
    alert('Connection to server is close')
    conn = null;
};

// Send in ws message with API format
function sendRequest(action, data_id) {
    json = JSON.stringify({"action":action, "data_id": data_id});
    conn.send(json);
}

// Functions for updates
function updateTicker(exchange_and_pair, data) {
    var symbolsTable = document.getElementById('symbols_rows');

    for (var i=0; i < symbolsTable.rows.length; i++) {
        pair = $('#symbols_rows tr').eq(i).find(".pair").text();

        if (pair == exchange_and_pair) {
            $('#symbols_rows tr').eq(i).find(".bid").text(data[0]);
            $('#symbols_rows tr').eq(i).find(".ask").text(data[1]);
            return;
        }
    }
}

// Full update chart
function setCandles(candles) {
    ohlc = [];
    vol = [];
    var time = 0;
    for (var i = 0; i < candles.length; i++) {
        time = candles[i][5]
        ohlc.push([time, parseFloat(candles[i][0]), parseFloat(candles[i][1]), parseFloat(candles[i][2]),
                  parseFloat(candles[i][3])]);
        vol.push([time, parseFloat(candles[i][4])]);
    }

    lastTime = time;
    chart.series[0].setData(ohlc);
    chart.series[1].setData(vol);
}

// update last candles or append new candles
function updateCandle(candle) {
    var time = candle[5]

    // if time not update, delete last candle and volume bar
    if (lastTime == time)
    {
        ohlc = ohlc.filter(function(value, index, arr){
            return value[0] != lastTime;
        });
        vol = vol.filter(function(value, index, arr){
            return value[0] != lastTime;
        });
    }

    ohlc.push([time, parseFloat(candle[0]), parseFloat(candle[1]),
              parseFloat(candle[2]), parseFloat(candle[3])]
    );
    vol.push([time, parseFloat(candle[4])]);

    chart.series[0].setData(ohlc);
    chart.series[1].setData(vol);

    lastTime = time;
}

function updateDepth(data) {
    htmlChilds = '';
    bids = data[0];
    asks = data[1];

    for (var i = 0; i < asks.length; i++) {
        htmlChilds += "<tr style=\" background: #FD8080\"><td>" + asks[i][0] + "</td><td>" + asks[i][1] + "</td></tr>";
    }

    for (var i = 0; i < bids.length; i++) {
        htmlChilds += "<tr style=\"background: #73F182\"><td>" + bids[i][0] + "</td><td>" + bids[i][1] + "</td></tr>";
    }

    document.getElementById('content_market_depth').innerHTML = htmlChilds;
}

function updateListing(data) {
    listing = data

    document.getElementById("exchanges_combobox").removeAttribute("disabled");
    document.getElementById("input_symbols_combobox").removeAttribute("disabled");
    document.getElementById("time_frames_combobox").removeAttribute("disabled");
    document.getElementById("delete_button").removeAttribute("disabled");

    exchanges = Object.keys(listing)
    htmlChilds = '';
    for (var i = 0; i < exchanges.length; i++) {
        htmlChilds += '<option value="' + exchanges[i] + '">' + exchanges[i] + '</option>';
    }
    document.getElementById('exchanges_combobox').innerHTML = htmlChilds;
    exchange = exchanges[0]
    $("#exchanges_combobox").val(exchange);

    symbols = data[exchange][1]
    htmlChilds = '<option value=""></option>';
    for (var i = 0; i < symbols.length; i++) {
        htmlChilds += '<option value="' + symbols[i] + '">' + symbols[i] + '</option>';
    }
    document.getElementById('symbols_combobox').innerHTML = htmlChilds;
    $("#input_symbols_combobox").val('');
}

function errorMsg(data_id, msg) {
    alert('Server error: ' + msg)

    fragment_id = data_id.split('.')
    var errDataType = fragment_id[1],
        errExchange = fragment_id[2],
        errPair = fragment_id[3];

    if (errDataType == DATA_TYPE_TICKER) {
        var symbolsTable = document.getElementById('symbols_rows');
        for (var i=0; i < symbolsTable.rows.length; i++) {
            pair = $('#symbols_rows tr').eq(i).find(".pair").text();

            if (pair == errExchange + ' | ' + err_pair) {
                $('#symbols_rows tr').eq(i).remove()
            }
        }
    }
    else {
        if (errPair == chartPair && errExchange == chartExchange)
        {
            if (errDataType == DATA_TYPE_DEPTH) {
                document.getElementById("content_market_depth").innerHTML = ''
            }
            else {
                if (errDataType == DATA_TYPE_CANDLES) {
                    chart = Highcharts.stockChart('ohlc_chart', {
            title: {text: 'Select pair'},
            rangeSelector: {enabled:false},
            yAxis: [{
                labels: {
                    align: 'right',
                    x: -3
                },
                title: {
                    text: 'OHLC'
                },
                    height: '60%',
                    lineWidth: 2
                },
                {
                    labels: {
                        align: 'right',
                        x: -3
                    },
                    title: {
                        text: 'Volume'
                    },
                    top: '65%',
                    height: '35%',
                    offset: 0,
                    lineWidth: 2
                }],

            tooltip: {
                split: true
            },

            series: [{
                    type: 'candlestick',
                    name: 'candles'
                },
                {
                    type: 'column',
                    name: 'volumes',
                    yAxis: 1
                }]
        });
                }
            }
        }
    }
}

function changeExchange(selectObject) {
    if (selectObject.value == exchange) {
        return;
    }

    exchange = selectObject.value;
    var pairs = listing[exchange][1];

    htmlChilds = '<option value=""></option>';
    for (var i = 0; i < pairs.length; i++) {
        htmlChilds += '<option value="' + pairs[i] + '">' + pairs[i] + '</option>';
    }

    document.getElementById('symbols_combobox').innerHTML = htmlChilds;
    $("#input_symbols_combobox").val('');
}

function changeTimeFrame(selectObject) {
    request = DATA_TYPE_CANDLES + '.' + chartExchange + "." + chartPair + "." + timeFrame;
    sendRequest(ACTION_UNSUB, request)

    timeFrame = selectObject.value;
    request = DATA_TYPE_CANDLES + '.' + chartExchange + "." + chartPair + "." + timeFrame;
    sendRequest(ACTION_SUB, request)
}

function clickToSymbol(){
    if ($(this).find('td:first').html() == selectedPair) { return; }

    $(this).addClass('selected').siblings().removeClass('selected');
    selectedPair=$(this).find('td:first').html();
    selectedRow=$(this);
}

function doubleClickToSymbol(){
    var selectedExchange = selectedPair.split(' | ')[0],
        selectedSymbol = selectedPair.split(' | ')[1];
    // If select pair that already to char return
    if (chartPair == selectedSymbol && chartExchange == selectedExchange) { return; }

    if (chartPair != '' && chartExchange != '') {
        request = DATA_TYPE_DEPTH + '.' + chartExchange + '.' + chartPair;
        sendRequest(ACTION_UNSUB, request)
        request = DATA_TYPE_CANDLES + '.' + chartExchange + '.' + chartPair + '.' + timeFrame;
        sendRequest(ACTION_UNSUB, request)
    }

    // if chart is empty or select other exchange, change time frame
    if (chartPair == '' || selectedExchange != exchange){
        var timeFrames = listing[selectedExchange][0],
            htmlChilds = '';
        for (var i = 0; i < listing[exchange][0].length; i++) {
            htmlChilds += '<option value="' + listing[exchange][0][i] + '">' + listing[exchange][0][i] + '</option>';
        }

        document.getElementById('time_frames_combobox').innerHTML = htmlChilds;
        timeFrame = listing[exchange][0][0]
        $("#time_frames_combobox").val(timeFrame);
    }

    chartExchange = selectedExchange;
    chartPair = selectedSymbol;

    request = DATA_TYPE_DEPTH + '.' + chartExchange + '.' + chartPair;
    sendRequest(ACTION_SUB, request)
    request = DATA_TYPE_CANDLES + '.' + chartExchange + '.' + chartPair + '.' + timeFrame;
    sendRequest(ACTION_SUB, request)
}

function buttonDeleteClick() {
    if (selectedPair == '' || selectedRow == null) { return }
    selectedRow.remove();

    var selectedExchange = selectedPair.split(' | ')[0],
        selectedSymbol = selectedPair.split(' | ')[1];

    request = DATA_TYPE_TICKER + '.' + selectedExchange + '.' + selectedSymbol;
    sendRequest(ACTION_UNSUB, request)

    if (selectedSymbol == chartPair && selectedExchange == chartExchange) {
        request = DATA_TYPE_CANDLES + '.' + chartExchange + '.' + chartPair + '.' + timeFrame;
        sendRequest(ACTION_UNSUB, request)

        request = DATA_TYPE_DEPTH + '.' + chartExchange + '.' + chartPair;
        sendRequest(ACTION_UNSUB, request)

        chartPair = ''
        chartExchange = ''
        chart = Highcharts.stockChart('ohlc_chart', {
            title: {text: 'Select pair'},
            rangeSelector: {enabled:false},
            yAxis: [{
                labels: {
                    align: 'right',
                    x: -3
                },
                title: {
                    text: 'OHLC'
                },
                    height: '60%',
                    lineWidth: 2
                },
                {
                    labels: {
                        align: 'right',
                        x: -3
                    },
                    title: {
                        text: 'Volume'
                    },
                    top: '65%',
                    height: '35%',
                    offset: 0,
                    lineWidth: 2
                }],

            tooltip: {
                split: true
            },

            series: [{
                    type: 'candlestick',
                    name: 'candles'
                },
                {
                    type: 'column',
                    name: 'volumes',
                    yAxis: 1
                }]
        });

        document.getElementById("content_market_depth").innerHTML = ''
        document.getElementById("time_frames_combobox").innerHTML = ''
    }
    selectedPair = '';
}

// Select new pair
$(document).on('change', 'input', function(){
    var options = $('datalist')[0].options;
    var symbol = '';
    for (var i=0; i<options.length; i++) {
        if (options[i].value == $(this).val()) {
            symbol = $(this).val();
            break;
        }
    }

    symbols_from_table = document.getElementById("symbols_rows").innerHTML
    exchange_symbols = listing[exchange][1]
    pair_in_table = '>' + exchange + ' | ' + symbol + '<'

    if (symbol != '' && exchange_symbols.includes(symbol) && !symbols_from_table.includes(pair_in_table)) {
        var new_row = '<tr><td class="pair">' + exchange + ' | ' + symbol + '</td><td class="bid">-</td><td class="ask">-</td></tr>'
        document.getElementById("symbols_rows").innerHTML += new_row;
        $("#symbols_rows tr").click(clickToSymbol);
        $("#symbols_rows tr").dblclick(doubleClickToSymbol);
        request = DATA_TYPE_TICKER + '.' + exchange + '.' + symbol;
        sendRequest(ACTION_SUB, request)
    }

    $('#input_symbols_combobox').val('');
});

$(document).ready(function(){
    $("input").click(function(){
        $(this).next().show();
        $(this).next().hide();
    });
});
