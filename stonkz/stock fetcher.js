async function renderStocks() {
  const tableBody = document.getElementById("stockTable").querySelector("tbody");
  tableBody.innerHTML = "";

  const response = await fetch("http://127.0.0.1:5000/stocks");
  const stockData = await response.json();

  // Sort stocks by percentage change in descending order
  stockData.sort((a, b) => b.change - a.change);

  stockData.forEach(stock => {
    const row = document.createElement("tr");

    row.innerHTML = `
      <td>${stock.ticker}</td>
      <td>${stock.price.toFixed(2)}</td>
      <td>${stock.volume.toLocaleString()}</td>
      <td class="${stock.change >= 0 ? 'positive' : 'negative'}">${stock.change.toFixed(2)}%</td>
    `;

    tableBody.appendChild(row);
  });
}

// Initial render
renderStocks();
setInterval(renderStocks, 60000); // Auto-refresh every 60 seconds
