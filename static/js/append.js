// document.write('<script src="js/echarts.common.min.js"></script>');

function append_data(store_data, chart)
{
    var option = {
        title: {
            text: "position"
        },
        tooltip: {},
        xAxis:{},
        yAxis:{},
        series:[]
    };
    chart.setOption(option);
    
    var websock = new WebSocket("ws://localhost:8080/web/");

    websock.onmessage = function(evt)
    {
        var i;
        var res = evt.data;
        var pos_data = JSON.parse(res);
        if (store_data.length) {
            for (i = 0; i < store_data.length;i ++) {
                if (store_data[i].id == pos_data["id"]) {
                    // 有相同的
                    store_data[i].x = pos_data["x"];
                    store_data[i].y = pos_data["y"];
                    chart.setOption({
                        series:[{
                            type: "scatter",
                            name: pos_data["id"],
                            data: [pos_data["x"], pos_data["y"]]
                        }]
                    });
                    return;
                }
            }
        }
        var data = {id: pos_data["id"], x: pos_data["x"], y: pos_data["y"]};
        store_data.push(data);      //添加进列表中
        chart.setOption({
            series:[{
                type: "scatter",
                name: pos_data["id"],
                data: [pos_data["x"], pos_data["y"]]
            }]
        });
    };
}