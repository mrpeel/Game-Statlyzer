document.addEventListener("DOMContentLoaded", async () => {
    const select = document.getElementById("gameSelect");
    const scorecardPanel = document.getElementById("scorecardContent");
    const milestonesPanel = document.getElementById("milestonesContent");
    const bbbPanel = document.getElementById("bbbContent");

    const scorecardStatus = document.getElementById("scorecardStatus");
    const milestonesStatus = document.getElementById("milestonesStatus");
    const bbbStatus = document.getElementById("bbbStatus");

    let gameData = [];

    // Load the mapping data
    try {
        // fetch cache buster to always get fresh json
        const response = await fetch("data_map.json?" + new Date().getTime());
        gameData = await response.json();
        
        gameData.forEach((game, index) => {
            const option = document.createElement("option");
            option.value = index;
            option.textContent = game.name;
            select.appendChild(option);
        });
    } catch (err) {
        console.error("Failed to load data_map.json", err);
        select.innerHTML = '<option>Error loading games list</option>';
    }

    select.addEventListener("change", async (e) => {
        const index = e.target.value;
        if (index === "") return;

        const game = gameData[index];
        
        // Reset panels
        scorecardStatus.className = "status-badge status-wait";
        scorecardStatus.textContent = "Loading...";
        scorecardPanel.innerHTML = '<div class="placeholder">Loading...</div>';

        milestonesStatus.className = "status-badge status-wait";
        milestonesStatus.textContent = "Loading...";
        milestonesPanel.innerHTML = '<div class="placeholder">Loading...</div>';

        bbbStatus.className = "status-badge status-wait";
        bbbStatus.textContent = "Loading...";
        bbbPanel.innerHTML = '<div class="placeholder">Loading...</div>';

        // Fetch Markdown Scorecard
        if (game.scorecard) {
            try {
                const res = await fetch(`../${game.scorecard}`);
                if (res.ok) {
                    const text = await res.text();
                    scorecardPanel.innerHTML = marked.parse(text);
                    scorecardStatus.className = "status-badge ok";
                    scorecardStatus.textContent = "Loaded";
                } else {
                    throw new Error("File not found");
                }
            } catch (err) {
                scorecardPanel.innerHTML = `<div class="placeholder">Error loading scorecard</div>`;
                scorecardStatus.className = "status-badge warn";
                scorecardStatus.textContent = "Error";
            }
        } else {
            scorecardPanel.innerHTML = `<div class="placeholder">No scorecard available</div>`;
            scorecardStatus.className = "status-badge warn";
            scorecardStatus.textContent = "Missing";
        }

        // Fetch Milestones
        if (game.milestones) {
            try {
                const res = await fetch(`../${game.milestones}`);
                if (res.ok) {
                    const text = await res.text();
                    renderCSV(text, milestonesPanel);
                    milestonesStatus.className = "status-badge ok";
                    milestonesStatus.textContent = "Loaded";
                } else {
                    throw new Error("File not found");
                }
            } catch (err) {
                milestonesPanel.innerHTML = `<div class="placeholder">Error loading milestones</div>`;
                milestonesStatus.className = "status-badge warn";
                milestonesStatus.textContent = "Error";
            }
        } else {
            milestonesPanel.innerHTML = `<div class="placeholder">No milestones available</div>`;
            milestonesStatus.className = "status-badge warn";
            milestonesStatus.textContent = "Missing";
        }

        // Fetch Ball by Ball
        if (game.ball_by_ball) {
            try {
                const res = await fetch(`../${game.ball_by_ball}`);
                if (res.ok) {
                    const text = await res.text();
                    
                    // Simple check if Laburnum data is inside
                    if (!text.includes("Laburnum")) {
                        renderCSV(text, bbbPanel);
                        bbbStatus.className = "status-badge warn";
                        bbbStatus.textContent = "No Laburnum Data";
                    } else {
                        renderCSV(text, bbbPanel);
                        bbbStatus.className = "status-badge ok";
                        bbbStatus.textContent = "Loaded";
                    }
                } else {
                    throw new Error("File not found");
                }
            } catch (err) {
                bbbPanel.innerHTML = `<div class="placeholder">Error loading ball-by-ball</div>`;
                bbbStatus.className = "status-badge warn";
                bbbStatus.textContent = "Error";
            }
        } else {
            bbbPanel.innerHTML = `<div class="placeholder">No ball-by-ball data</div>`;
            bbbStatus.className = "status-badge warn";
            bbbStatus.textContent = "Missing";
        }
    });

    function renderCSV(csvText, container) {
        Papa.parse(csvText, {
            header: true,
            skipEmptyLines: true,
            complete: function(results) {
                if (results.data.length === 0) {
                    container.innerHTML = '<div class="placeholder">Empty CSV file</div>';
                    return;
                }

                let html = '<table><thead><tr>';
                const headers = Object.keys(results.data[0]);
                headers.forEach(h => html += `<th>${h}</th>`);
                html += '</tr></thead><tbody>';

                results.data.forEach(row => {
                    html += '<tr>';
                    headers.forEach(h => html += `<td>${row[h]}</td>`);
                    html += '</tr>';
                });
                
                html += '</tbody></table>';
                container.innerHTML = html;
            }
        });
    }
});
