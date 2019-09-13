window.chartColors = {
  red: 'rgb(255, 99, 132)',
  orange: 'rgb(255, 159, 64)',
  yellow: 'rgb(255, 205, 86)',
  green: 'rgb(75, 192, 192)',
  blue: 'rgb(54, 162, 235)',
  purple: 'rgb(153, 102, 255)',
  grey: 'rgb(201, 203, 207)'
};

$(document).ready(function() {
  var labels = [];
  var data = [];
  var info = loadData(labels, data);

  var ctx = document.getElementById('myChart').getContext('2d');
  ctx.canvas.height = 100;

  var color = Chart.helpers.color;
  var cfg = {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: info[0],
        backgroundColor: color(window.chartColors.red).alpha(0.5).rgbString(),
        borderColor: window.chartColors.red,
        data: data,
        type: 'line',
        pointRadius: 0,
        fill: false,
        lineTension: 0,
        borderWidth: 2
      }]
    },
    options: {
      scales: {
        xAxes: [{
          distribution: 'series',
          ticks: {
            source: 'labels'
          }
        }],
        yAxes: [{
          scaleLabel: {
            display: true,
            labelString: info[1]
          }
        }]
      }
    }
  };
  new Chart(ctx, cfg);
});
