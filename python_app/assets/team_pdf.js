/**
 * One-click team report, merged in the browser.
 *
 * Rendering a whole roster server-side was one request minutes long: High Point
 * (34 pitchers) 504'd at the ALB's 300s idle timeout and Charleston needed 173.5s
 * against a 180s worker timeout. Here the browser asks for one page at a time and
 * merges them with pdf-lib, so no single request is long, a pitcher who fails
 * costs one page instead of the report, and the wait is visible.
 *
 * Fetches are deliberately SEQUENTIAL. The worker runs `--workers 1 --threads 2`,
 * and page rendering is serialised behind a lock anyway (pyplot and kaleido are
 * process-global), so parallel requests would only queue — while making an
 * overlapping-render bug easier to hit.
 */
(function () {
  /** Dash's own prefix, so the URLs work at "/" in dev and "/widgets/pitching/" in prod. */
  function basePath() {
    try {
      const cfg = JSON.parse(document.getElementById('_dash-config').textContent);
      return cfg.requests_pathname_prefix || '/';
    } catch (err) {
      return './';
    }
  }

  function setStatus(text) {
    if (window.dash_clientside && window.dash_clientside.set_props) {
      window.dash_clientside.set_props('team-pdf-status', { children: text });
    }
  }

  function setButton(props) {
    if (window.dash_clientside && window.dash_clientside.set_props) {
      window.dash_clientside.set_props('download-team-pdf-btn', props);
    }
  }

  function saveBlob(bytes, filename) {
    const href = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' }));
    const link = document.createElement('a');
    link.href = href;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(href);
  }

  window.dash_clientside = Object.assign({}, window.dash_clientside, {
    teamPdf: {
      /**
       * @param {number} nClicks   Team PDF button clicks.
       * @param {string} team      Selected team ("__ALL_TEAMS__" is not exportable).
       * @param {string} tag       Pitch-tagging radio.
       * @param {string} side      Batter-side radio.
       * @returns {Promise<string>} Status line for #team-pdf-status.
       */
      run: async function (nClicks, team, tag, side) {
        if (!nClicks || !team || team === '__ALL_TEAMS__') {
          return window.dash_clientside.no_update;
        }
        if (typeof PDFLib === 'undefined') {
          return 'Team PDF needs the pdf-lib library, which failed to load. ' +
            'Use the one-page PDF button, or reload the page.';
        }

        const base = basePath();
        const query = `tag=${encodeURIComponent(tag || 'auto_pitch_type')}` +
          `&side=${encodeURIComponent(side || 'All')}`;

        setButton({ disabled: true });
        setStatus('Building team report…');

        try {
          const rosterResp = await fetch(
            `${base}api/team-roster?team=${encodeURIComponent(team)}`
          );
          if (!rosterResp.ok) {
            return `Could not load the ${team} roster (${rosterResp.status}).`;
          }
          const roster = await rosterResp.json();
          const players = roster.players || [];
          if (players.length === 0) {
            return `No pitchers on the ${team} roster to export.`;
          }

          const merged = await PDFLib.PDFDocument.create();
          const failed = [];

          for (let i = 0; i < players.length; i++) {
            setStatus(`Building team report — ${i} of ${players.length} pages…`);
            try {
              const resp = await fetch(
                `${base}api/player-pdf?guid=${encodeURIComponent(players[i].id)}&${query}`
              );
              if (!resp.ok) {
                failed.push(players[i].name);
                continue;
              }
              const page = await PDFLib.PDFDocument.load(await resp.arrayBuffer());
              const copied = await merged.copyPages(page, page.getPageIndices());
              copied.forEach((p) => merged.addPage(p));
            } catch (err) {
              failed.push(players[i].name);
            }
          }

          const pages = merged.getPageCount();
          if (pages === 0) {
            return `No pages could be built for ${team}. Nothing was downloaded.`;
          }

          const sideSuffix = side === 'Right' ? ' vs RHB' : side === 'Left' ? ' vs LHB' : '';
          saveBlob(await merged.save(), `${team} Pitching Reports${sideSuffix}.pdf`);

          // Name who is missing. "31 pages" alone reads as a complete roster.
          let status = `Downloaded ${pages} page${pages === 1 ? '' : 's'}.`;
          if (failed.length) {
            status += ` ${failed.length} could not be built: ${failed.join(', ')}.`;
          }
          if (roster.excluded) {
            status += ` ${roster.excluded} roster record${roster.excluded === 1 ? '' : 's'} ` +
              'had no player id and could not be exported.';
          }
          return status;
        } catch (err) {
          return `Team PDF failed: ${err.message}`;
        } finally {
          setButton({ disabled: false });
        }
      },
    },
  });
})();
