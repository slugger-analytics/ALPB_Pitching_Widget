/* ALPB Pitching Widget - Pure JS MVP for GitHub Pages */

const CFG = {
  POINTSTREAK_API_KEY: "",
  POINTSTREAK_BASE_URL: "https://api.pointstreak.com/baseball",
  LEAGUE_ID: "174",
  ALPB_API_KEY: "",
  ALPB_BASE_URL: "https://1ywv9dczq5.execute-api.us-east-2.amazonaws.com/ALPBAPI",
  SEASON_ID: "34104",
  ALL_TEAMS: "__ALL_TEAMS__",
  EXCLUDED_TEAMS: new Set(["California Dogecoin", "Long Island Black Sox"]),
  MAX_PITCH_PAGES: 120,
};

const PITCH_COLORS = {
  Fastball: "#ef4444",
  "Four-Seam": "#ef4444",
  Changeup: "#3b82f6",
  ChangeUp: "#3b82f6",
  Sinker: "#16a34a",
  Curveball: "#a16207",
  Slider: "#7c3aed",
  Splitter: "#111827",
  Cutter: "#ec4899",
  Untagged: "#6b7280",
};

const AXIS_LABELS = {
  induced_vert_break: "Induced Vertical Break (in)",
  horz_break: "Horizontal Break (in)",
  rel_speed: "Velocity (mph)",
};

const state = {
  roster: [],
  selectedTeam: CFG.ALL_TEAMS,
  selectedPlayerLinkId: null,
  breakAxis: "induced_vert_break",
  tagChoice: "auto_pitch_type",
  selectedPitchType: "All",
  seasonStatsCache: new Map(),
  alpbIdCache: new Map(),
  pitchDataCache: new Map(),
  currentPitches: [],
};

const ui = {
  teamSelect: document.getElementById("team-select"),
  playerSelect: document.getElementById("player-select"),
  tagChoice: document.getElementById("tag-choice"),
  pitchTypeSelect: document.getElementById("pitch-type-select"),
  reloadBtn: document.getElementById("reload-btn"),
  statusChip: document.getElementById("status-chip"),
  notice: document.getElementById("notice"),
  playerInfo: document.getElementById("player-info"),
  seasonStats: document.getElementById("season-stats"),
  pitchSplit: document.getElementById("pitch-split"),
};

function setStatus(text, kind = "ok") {
  ui.statusChip.textContent = text;
  ui.statusChip.classList.remove("warn", "error");
  if (kind === "warn") ui.statusChip.classList.add("warn");
  if (kind === "error") ui.statusChip.classList.add("error");
}

function setNotice(text, isError = false) {
  ui.notice.textContent = text;
  ui.notice.classList.toggle("error", isError);
}

function asArray(v) {
  if (Array.isArray(v)) return v;
  if (v && typeof v === "object") return [v];
  return [];
}

function safeStr(v) {
  if (v == null) return "";
  return String(v);
}

function esc(v) {
  return safeStr(v)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

async function fetchJson(url, headers = {}) {
  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} on ${url}`);
  }
  return res.json();
}

function getSelectedPlayer() {
  return state.roster.find((p) => p.playerlinkid === state.selectedPlayerLinkId) || null;
}

function coerceNum(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function normalizedPitchType(v) {
  const token = safeStr(v).trim();
  if (!token || token === "Undefined") return null;
  return token;
}

async function loadRoster() {
  setStatus("Loading roster...");
  const structureUrl = `${CFG.POINTSTREAK_BASE_URL}/league/structure/${CFG.LEAGUE_ID}/json?seasonid=${CFG.SEASON_ID}`;
  const parsed = await fetchJson(structureUrl, { apikey: CFG.POINTSTREAK_API_KEY });

  const season = asArray(parsed?.league?.season).find(
    (s) => safeStr(s.seasonid) === safeStr(CFG.SEASON_ID),
  );
  if (!season) {
    throw new Error(`Season ${CFG.SEASON_ID} not found in league structure.`);
  }

  const teams = [];
  asArray(season.division).forEach((div) => {
    teams.push(...asArray(div.team));
  });

  const rosterChunks = await Promise.all(
    teams.map(async (team) => {
      const teamId = safeStr(team.teamlinkid).trim();
      const teamName = safeStr(team.teamname).trim();
      if (!teamId || CFG.EXCLUDED_TEAMS.has(teamName)) return [];

      const rosterUrl =
        `${CFG.POINTSTREAK_BASE_URL}/team/roster/` +
        `${encodeURIComponent(teamId)}/${encodeURIComponent(CFG.SEASON_ID)}/json`;
      try {
        const roster = await fetchJson(rosterUrl, { apikey: CFG.POINTSTREAK_API_KEY });
        return asArray(roster?.league?.player)
          .filter((p) => safeStr(p.position).trim() === "P")
          .map((p) => ({
            playerid: safeStr(p.playerid),
            playerlinkid: safeStr(p.playerlinkid),
            fname: safeStr(p.fname).trim(),
            lname: safeStr(p.lname).trim(),
            full_name: `${safeStr(p.fname).trim()} ${safeStr(p.lname).trim()}`.trim(),
            teamname: teamName,
            throws: safeStr(p.throws),
            bats: safeStr(p.bats),
            height: safeStr(p.height),
            weight: safeStr(p.weight),
            hometown: safeStr(p.hometown),
            photo: safeStr(p.photo),
          }));
      } catch {
        return [];
      }
    }),
  );

  const bad = new Set(["", "unknown", "nan", "none", "null", "/"]);
  const rows = rosterChunks
    .flat()
    .filter((p) => {
      const first = p.fname.toLowerCase();
      const last = p.lname.toLowerCase();
      return !bad.has(first) && !bad.has(last);
    })
    .sort((a, b) => (a.lname + a.fname).localeCompare(b.lname + b.fname));

  state.roster = rows;
}

function renderTeamOptions() {
  const teams = [...new Set(state.roster.map((p) => p.teamname).filter(Boolean))].sort();
  const options = [{ label: "All Teams", value: CFG.ALL_TEAMS }].concat(
    teams.map((team) => ({ label: team, value: team })),
  );

  ui.teamSelect.innerHTML = options
    .map((o) => `<option value="${esc(o.value)}">${esc(o.label)}</option>`)
    .join("");

  ui.teamSelect.value = state.selectedTeam;
}

function getVisiblePlayers() {
  if (state.selectedTeam === CFG.ALL_TEAMS) return state.roster;
  return state.roster.filter((p) => p.teamname === state.selectedTeam);
}

function renderPlayerOptions() {
  const players = getVisiblePlayers();
  const showTeam = state.selectedTeam === CFG.ALL_TEAMS;
  const options = players.map((p) => ({
    value: p.playerlinkid,
    label: showTeam ? `${p.full_name} (${p.teamname})` : p.full_name,
  }));

  ui.playerSelect.innerHTML = options
    .map((o) => `<option value="${esc(o.value)}">${esc(o.label)}</option>`)
    .join("");

  const valid = new Set(options.map((o) => o.value));
  if (!valid.has(state.selectedPlayerLinkId)) {
    state.selectedPlayerLinkId = options.length ? options[0].value : null;
  }
  ui.playerSelect.value = state.selectedPlayerLinkId || "";
}

function renderPlayerCard(player) {
  if (!player) {
    ui.playerInfo.innerHTML = '<p class="empty">Select a pitcher.</p>';
    return;
  }

  const fields = [
    ["Name", player.full_name],
    ["Team", player.teamname],
    ["Throws", player.throws],
    ["Bats", player.bats],
    ["Height", player.height],
    ["Weight", player.weight],
    ["Hometown", player.hometown],
  ].filter(([, v]) => safeStr(v).trim());

  const photo = player.photo
    ? `<img class="player-photo" src="${esc(player.photo)}" alt="${esc(player.full_name)}" />`
    : '<div class="player-photo"></div>';

  const rows = fields
    .map(([k, v]) => `<div class="row"><span class="k">${esc(k)}</span><span class="v">${esc(v)}</span></div>`)
    .join("");

  ui.playerInfo.innerHTML = `
    ${photo}
    <div class="player-meta">${rows}</div>
  `;
}

function renderTableFromRows(rows) {
  if (!rows || !rows.length) return '<p class="empty">No data available.</p>';
  const headers = Object.keys(rows[0]);
  const th = headers.map((h) => `<th>${esc(h)}</th>`).join("");
  const body = rows
    .map((row) => {
      const tds = headers.map((h) => `<td>${esc(row[h])}</td>`).join("");
      return `<tr>${tds}</tr>`;
    })
    .join("");
  return `<div class="table-wrap"><table><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table></div>`;
}

async function fetchSeasonStats(playerLinkId) {
  if (state.seasonStatsCache.has(playerLinkId)) {
    return state.seasonStatsCache.get(playerLinkId);
  }
  const url = `${CFG.POINTSTREAK_BASE_URL}/player/stats/${encodeURIComponent(playerLinkId)}/${encodeURIComponent(CFG.SEASON_ID)}/json`;
  try {
    const parsed = await fetchJson(url, { apikey: CFG.POINTSTREAK_API_KEY });
    const season = parsed?.player?.pitchingstats?.season;
    const rows = asArray(season);
    state.seasonStatsCache.set(playerLinkId, rows.length ? rows : null);
    return rows.length ? rows : null;
  } catch {
    state.seasonStatsCache.set(playerLinkId, null);
    return null;
  }
}

async function renderSeasonStats(player) {
  if (!player) {
    ui.seasonStats.innerHTML = '<p class="empty">Select a pitcher.</p>';
    return;
  }

  const stats = await fetchSeasonStats(player.playerlinkid);
  if (!stats) {
    ui.seasonStats.innerHTML = '<p class="empty">No season stats found.</p>';
    return;
  }

  const normalized = stats.map((row) => {
    const out = {};
    Object.keys(row).forEach((key) => {
      out[key.toUpperCase()] = row[key];
    });
    return out;
  });
  ui.seasonStats.innerHTML = renderTableFromRows(normalized);
}

async function lookupAlpbId(player) {
  const key = safeStr(player?.playerlinkid);
  if (!key) return null;
  if (state.alpbIdCache.has(key)) return state.alpbIdCache.get(key);

  const query = `${safeStr(player.lname)}, ${safeStr(player.fname)}`;
  const url = `${CFG.ALPB_BASE_URL}/players?player_name=${encodeURIComponent(query)}`;
  try {
    const parsed = await fetchJson(url, { "x-api-key": CFG.ALPB_API_KEY });
    const found = asArray(parsed?.data).find((p) => Boolean(p?.is_pitcher));
    const id = found?.player_id ? safeStr(found.player_id) : null;
    state.alpbIdCache.set(key, id);
    return id;
  } catch {
    state.alpbIdCache.set(key, null);
    return null;
  }
}

async function fetchPitchData(alpbPlayerId) {
  if (!alpbPlayerId) return [];
  if (state.pitchDataCache.has(alpbPlayerId)) {
    return state.pitchDataCache.get(alpbPlayerId);
  }

  const all = [];
  for (let page = 1; page <= CFG.MAX_PITCH_PAGES; page += 1) {
    const url =
      `${CFG.ALPB_BASE_URL}/pitches?pitcher_id=` +
      `${encodeURIComponent(alpbPlayerId)}&page=${page}`;
    let parsed;
    try {
      parsed = await fetchJson(url, { "x-api-key": CFG.ALPB_API_KEY });
    } catch {
      break;
    }
    const rows = asArray(parsed?.data);
    if (!rows.length) break;
    all.push(...rows);
  }

  state.pitchDataCache.set(alpbPlayerId, all);
  return all;
}

function buildScatterFigure(records, xAxis, yAxis, tag) {
  const grouped = new Map();
  records.forEach((r) => {
    const x = coerceNum(r[xAxis]);
    const y = coerceNum(r[yAxis]);
    if (x == null || y == null) return;
    const rawTag = normalizedPitchType(r[tag]);
    const key = rawTag || "Untagged";
    if (!grouped.has(key)) grouped.set(key, { x: [], y: [] });
    grouped.get(key).x.push(x);
    grouped.get(key).y.push(y);
  });

  const traces = [...grouped.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([name, xy]) => ({
      type: "scatter",
      mode: "markers",
      name,
      x: xy.x,
      y: xy.y,
      marker: { size: 6, opacity: 0.72, color: PITCH_COLORS[name] || "#6b7280" },
    }));

  return {
    data: traces,
    layout: {
      margin: { l: 48, r: 18, t: 20, b: 48 },
      xaxis: { title: AXIS_LABELS[xAxis] || xAxis },
      yaxis: { title: AXIS_LABELS[yAxis] || yAxis },
      legend: { orientation: "h", y: -0.25 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "#ffffff",
    },
  };
}

function drawPlot(targetId, figure) {
  Plotly.react(targetId, figure.data, figure.layout, {
    displayModeBar: false,
    responsive: true,
  });
}

function buildHeatmapFigure(records) {
  const points = records
    .map((r) => ({
      x: coerceNum(r.plate_loc_side),
      y: coerceNum(r.plate_loc_height),
    }))
    .filter((p) => p.x != null && p.y != null);

  const traces = [];
  if (points.length >= 2) {
    traces.push({
      type: "histogram2d",
      x: points.map((p) => p.x),
      y: points.map((p) => p.y),
      xbins: { start: -1.5, end: 1.5, size: 0.06 },
      ybins: { start: 0, end: 4, size: 0.07 },
      colorscale: [
        [0, "#ffffff"],
        [0.25, "#5ca8ff"],
        [0.5, "#2dd4bf"],
        [0.75, "#facc15"],
        [1, "#ef4444"],
      ],
      showscale: false,
      hovertemplate: "x:%{x:.2f}<br>y:%{y:.2f}<extra></extra>",
    });
  }

  traces.push({
    type: "scatter",
    mode: "lines",
    x: [-10 / 12, 10 / 12, 10 / 12, -10 / 12, -10 / 12],
    y: [1.5, 1.5, 3.5, 3.5, 1.5],
    line: { color: "#111827", width: 2 },
    showlegend: false,
    hoverinfo: "skip",
  });

  return {
    data: traces,
    layout: {
      margin: { l: 10, r: 10, t: 10, b: 10 },
      xaxis: {
        range: [-16 / 12, 16 / 12],
        showgrid: false,
        zeroline: false,
        showticklabels: false,
      },
      yaxis: {
        range: [1, 4],
        showgrid: false,
        zeroline: false,
        showticklabels: false,
        scaleanchor: "x",
        scaleratio: 1,
      },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "#ffffff",
    },
  };
}

function filteredPitchesForCharts(side = null) {
  let rows = [...state.currentPitches];
  if (side) {
    rows = rows.filter((r) => safeStr(r.batter_side) === side);
  }
  if (state.selectedPitchType !== "All") {
    rows = rows.filter(
      (r) => normalizedPitchType(r[state.tagChoice]) === state.selectedPitchType,
    );
  }
  return rows;
}

function updatePitchTypeOptions() {
  const types = [...new Set(
    state.currentPitches
      .map((r) => normalizedPitchType(r[state.tagChoice]))
      .filter(Boolean),
  )].sort();

  const options = [{ value: "All", label: "All" }].concat(
    types.map((t) => ({ value: t, label: t })),
  );
  ui.pitchTypeSelect.innerHTML = options
    .map((o) => `<option value="${esc(o.value)}">${esc(o.label)}</option>`)
    .join("");

  const valid = new Set(options.map((o) => o.value));
  if (!valid.has(state.selectedPitchType)) state.selectedPitchType = "All";
  ui.pitchTypeSelect.value = state.selectedPitchType;
}

function renderPitchSplit() {
  if (!state.currentPitches.length) {
    ui.pitchSplit.innerHTML = '<p class="empty">No pitch split data available.</p>';
    return;
  }

  const grouped = new Map();
  state.currentPitches.forEach((row) => {
    const balls = coerceNum(row.balls);
    const strikes = coerceNum(row.strikes);
    const pitchType = normalizedPitchType(row[state.tagChoice]);
    if (balls == null || strikes == null || !pitchType) return;
    const count = `${balls} - ${strikes}`;
    if (!grouped.has(count)) grouped.set(count, new Map());
    const pitchMap = grouped.get(count);
    pitchMap.set(pitchType, (pitchMap.get(pitchType) || 0) + 1);
  });

  const pitchTypes = [...new Set(
    [...grouped.values()].flatMap((m) => [...m.keys()]),
  )].sort();

  const rows = [...grouped.entries()]
    .map(([count, pitchMap]) => {
      const [b, s] = count.split(" - ").map((v) => Number(v));
      const total = [...pitchMap.values()].reduce((a, b2) => a + b2, 0);
      const row = { Count: count, __b: b, __s: s };
      pitchTypes.forEach((pt) => {
        const pct = total ? ((pitchMap.get(pt) || 0) / total) * 100 : 0;
        row[pt] = pct.toFixed(1);
      });
      return row;
    })
    .sort((a, b) => a.__b - b.__b || a.__s - b.__s)
    .map(({ __b, __s, ...rest }) => rest);

  ui.pitchSplit.innerHTML = renderTableFromRows(rows);
}

function renderCharts() {
  const all = state.currentPitches || [];

  drawPlot(
    "chart-vel",
    buildScatterFigure(all, "rel_speed", state.breakAxis, state.tagChoice),
  );
  drawPlot(
    "chart-break",
    buildScatterFigure(all, "horz_break", "induced_vert_break", state.tagChoice),
  );
  drawPlot("heatmap-right", buildHeatmapFigure(filteredPitchesForCharts("Right")));
  drawPlot("heatmap-left", buildHeatmapFigure(filteredPitchesForCharts("Left")));
  renderPitchSplit();
}

async function refreshPlayerData() {
  const player = getSelectedPlayer();
  renderPlayerCard(player);
  await renderSeasonStats(player);

  if (!player) {
    state.currentPitches = [];
    updatePitchTypeOptions();
    renderCharts();
    return;
  }

  setStatus(`Loading pitch data for ${player.full_name}...`);
  const alpbId = await lookupAlpbId(player);
  if (!alpbId) {
    setStatus("No ALPB Trackman ID found for this player.", "warn");
    state.currentPitches = [];
    updatePitchTypeOptions();
    renderCharts();
    return;
  }

  const pitches = await fetchPitchData(alpbId);
  state.currentPitches = pitches;
  updatePitchTypeOptions();
  renderCharts();

  if (!pitches.length) {
    setStatus(`No pitch-level data found for ${player.full_name}.`, "warn");
  } else {
    setStatus(`Loaded ${pitches.length} pitches for ${player.full_name}.`);
  }
}

function bindEvents() {
  ui.teamSelect.addEventListener("change", async (e) => {
    state.selectedTeam = e.target.value;
    renderPlayerOptions();
    await refreshPlayerData();
  });

  ui.playerSelect.addEventListener("change", async (e) => {
    state.selectedPlayerLinkId = e.target.value;
    await refreshPlayerData();
  });

  ui.tagChoice.addEventListener("change", (e) => {
    state.tagChoice = e.target.value;
    updatePitchTypeOptions();
    renderCharts();
  });

  ui.pitchTypeSelect.addEventListener("change", (e) => {
    state.selectedPitchType = e.target.value;
    renderCharts();
  });

  document.querySelectorAll("input[name='break-axis']").forEach((radio) => {
    radio.addEventListener("change", (e) => {
      state.breakAxis = e.target.value;
      renderCharts();
    });
  });

  ui.reloadBtn.addEventListener("click", async () => {
    state.seasonStatsCache.clear();
    state.alpbIdCache.clear();
    state.pitchDataCache.clear();
    await bootstrap();
  });
}

function explainLoadError(error) {
  const msg = safeStr(error?.message || error);
  if (msg.includes("Failed to fetch")) {
    return (
      "Network/CORS blocked browser requests to one or more APIs. " +
      "For production, use a server-side proxy (Cloudflare Worker, Vercel, Render)."
    );
  }
  return msg;
}

async function bootstrap() {
  try {
    if (!CFG.POINTSTREAK_API_KEY || !CFG.ALPB_API_KEY) {
      setStatus("Missing API key config", "error");
      setNotice(
        "Static MVP no longer embeds API keys. Use the deployed Dash backend link (Render) or a server-side proxy.",
        true,
      );
      return;
    }

    setNotice(
      "This is a browser-only MVP. If your API blocks cross-origin requests, charts may stay empty on GitHub Pages.",
      false,
    );
    setStatus("Loading roster...");
    await loadRoster();

    state.selectedTeam = CFG.ALL_TEAMS;
    renderTeamOptions();
    renderPlayerOptions();
    await refreshPlayerData();

    const teamCount = new Set(state.roster.map((p) => p.teamname)).size;
    setNotice(
      `Loaded ${state.roster.length} pitchers across ${teamCount} teams. ` +
      "If data is incomplete, click Reload Data.",
      false,
    );
  } catch (error) {
    setStatus("Data load failed", "error");
    setNotice(explainLoadError(error), true);
    ui.playerInfo.innerHTML = '<p class="empty">Unable to load player data.</p>';
    ui.seasonStats.innerHTML = '<p class="empty">Unable to load season stats.</p>';
    ui.pitchSplit.innerHTML = '<p class="empty">Unable to load pitch split.</p>';
    drawPlot("chart-vel", { data: [], layout: {} });
    drawPlot("chart-break", { data: [], layout: {} });
    drawPlot("heatmap-right", { data: [], layout: {} });
    drawPlot("heatmap-left", { data: [], layout: {} });
  }
}

bindEvents();
bootstrap();
