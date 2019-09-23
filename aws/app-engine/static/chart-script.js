// Read the data
var labels = [];
var values = [];
var alerts = [];
var info = loadData(labels, values, alerts);
var lines = [{name: 'data_line',
              color: 'grey',
              data: []
             },
             {name: 'alert_line',
              color: 'red',
              data: []
             }];
for(var i = 0; i < labels.length; i++) {
  lines[0].data.push({ date: new Date(labels[i]),
                       value: values[i] });

  lines[1].data.push({ date: new Date(labels[i]),
                       value: alerts[i] });
}

// Set the dimensions and margins of the graph
var margin = {top: 10, right: 30, bottom: 35, left: 35},
    width = 360 - margin.left - margin.right,
    height = 150 - margin.top - margin.bottom;

// Append the svg object to the body of the page
var svg = d3.select("#myChart")
  .append("svg")
    .attr("width", width + margin.left + margin.right)
    .attr("height", height + margin.top + margin.bottom)
  .append("g")
    .attr("transform",
          "translate(" + margin.left + "," + margin.top + ")");

// Add X axis --> it is a date format
var x = d3.scaleTime()
  .domain(d3.extent(lines[0].data, function(d) { return d.date; }))
  .range([ 0, width ]);
var xAxis = svg.append("g")
  .attr("transform", "translate(0," + height + ")")
  .call(d3.axisBottom(x));

// Add Y axis
var y = d3.scaleLinear()
  .domain([0, d3.max(lines[0].data, function(d) { return +d.value; })])
  .range([ height, 0 ]);
var yAxis = svg.append("g")
  .call(d3.axisLeft(y));

// Text label for the x axis
svg.append("text")             
   .attr("transform",
         "translate(" + (width / 2) + "," + 
                        (height + margin.top + 20) + ")")
   .style("text-anchor", "middle")
   .text(info[0]);

// text label for the y axis
svg.append("text")
   .attr("transform", "rotate(-90)")
   .attr("y", 0 - margin.left - 3)
   .attr("x", 0 - (height / 2))
   .attr("dy", "1em")
   .style("text-anchor", "middle")
   .text(info[1]); 

// Add a clipPath: everything out of this area won't be drawn.
var clip = svg.append("defs").append("svg:clipPath")
              .attr("id", "clip")
              .append("svg:rect")
              .attr("width", width )
              .attr("height", height )
              .attr("x", 0)
              .attr("y", 0);

// Add brushing
var brush = d3.brushX().extent([ [0,0], [width,height] ]).on("end", updateChart)

// Create the line variable: where both the line and the brush take place
var line = svg.append('g').attr("clip-path", "url(#clip)")

// Add the lines
lines.forEach(function(item) {
  line.append("path")
      .datum(item.data)
      .attr("class", item.name) // The class allows this line be modified later
      .attr("fill", "none")
      .attr("stroke", item.color)
      .attr("stroke-width", 1.5)
      .attr("d", d3.line()
        .defined(function(d) { return !isNaN(d.value); })
        .x(function(d) { return x(d.date) })
        .y(function(d) { return y(d.value) })
        )
})

// Add the brushing
line.append("g").attr("class", "brush").call(brush);

// A function that set idleTimeOut to null
var idleTimeout;
function idled() { idleTimeout = null; }

// A function that updates the chart for given boundaries
function updateChart() {
  // What are the selected boundaries?
  extent = d3.event.selection

  // If no selection, back to initial coordinate. Otherwise, update X axis
  // domain
  if (!extent){
    // This allows us to wait a little bit
    if (!idleTimeout) return idleTimeout = setTimeout(idled, 350);
    x.domain([4,8])
  }
  else {
    x.domain([ x.invert(extent[0]), x.invert(extent[1]) ])
    // This removes the grey brush area as soon as the selection has been done
    line.select(".brush").call(brush.move, null)
  }

  // Update axis and line positions
  xAxis.transition().duration(1000).call(d3.axisBottom(x))
  lines.forEach(function(item) {
    line.select('.' + item.name)
        .transition()
        .duration(1000)
        .attr("d", d3.line()
          .defined(function(d) { return !isNaN(d.value); })
          .x(function(d) { return x(d.date) })
          .y(function(d) { return y(d.value) })
        )
  })
}

// If the user double clicks, reinitialize the chart
svg.on("dblclick",function(){
  x.domain(d3.extent(lines[0].data, function(d) { return d.date; }))
  xAxis.transition().call(d3.axisBottom(x))
  lines.forEach(function(item) {
    line.select('.' + item.name)
        .transition()
        .attr("d", d3.line()
          .defined(function(d) { return !isNaN(d.value); })
          .x(function(d) { return x(d.date) })
          .y(function(d) { return y(d.value) })
        )
  })
});
