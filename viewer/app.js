const COURSE_URL = "/data/viewer/course.json";
const TRAJECTORIES_URL = "/data/viewer/trajectories.json";
const SPLITS_CANDIDATE_URLS = [
  "/data/real/raw/athlete_splits_real.json",
  "/data/real/raw/athlete_splits.json",
  "/data/synth/raw/athlete_splits.json",
];
const STATION_NAMES = {
  1: "SkiErg",
  2: "Sled Push",
  3: "Sled Pull",
  4: "Burpee",
  5: "Row",
  6: "Sandbag Lunges",
  7: "Wall Balls",
};

const canvas = document.getElementById("viewer-canvas");
const ctx = canvas.getContext("2d");
const statusEl = document.getElementById("status");
const timeEl = document.getElementById("time");
const playPauseBtn = document.getElementById("play-pause-btn");
const seekSlider = document.getElementById("seek-slider");
const speedSelect = document.getElementById("speed-select");
const athleteSelect = document.getElementById("athlete-select");
const rankTableBody = document.getElementById("rank-table-body");

const palette = ["#ff6b6b", "#4ecdc4", "#ffd93d", "#6c8cff", "#c77dff", "#95d5b2"];
const padding = 42;
const world = { minX: 0, maxX: 1, minY: 0, maxY: 1 };

function loadJson(url) {
  return fetch(url).then((res) => {
    if (!res.ok) {
      throw new Error(`Failed to load ${url}: HTTP ${res.status}`);
    }
    return res.json();
  });
}

async function loadBestSplits(athleteIds) {
  for (const url of SPLITS_CANDIDATE_URLS) {
    try {
      const payload = await loadJson(url);
      if (!Array.isArray(payload?.athletes)) continue;
      const ids = new Set(payload.athletes.map((item) => item.athlete_id));
      const overlap = athleteIds.filter((id) => ids.has(id)).length;
      if (overlap > 0) {
        return payload;
      }
    } catch (_error) {
      // Ignore and continue trying fallback split files.
    }
  }
  return null;
}

function getEventMap(splits) {
  const map = new Map();
  const ordered = [...splits].sort((a, b) => Number(a.timestamp) - Number(b.timestamp));
  ordered.forEach((split) => {
    const key = `${split.sensor_type}:${split.round ?? "none"}`;
    if (!map.has(key)) map.set(key, Number(split.timestamp));
  });
  return map;
}

function normalizeSplitsToElapsed(splits) {
  const ordered = [...splits].sort((a, b) => Number(a.timestamp) - Number(b.timestamp));
  if (!ordered.length) return ordered;
  const base = Number(ordered[0].timestamp);
  return ordered.map((split) => ({
    ...split,
    timestamp: Number(split.timestamp) - base,
  }));
}

function getEventTime(eventMap, sensorType, roundNum = null) {
  return eventMap.get(`${sensorType}:${roundNum ?? "none"}`);
}

function buildSectionTimelineForAthlete(splits) {
  const eventMap = getEventMap(normalizeSplitsToElapsed(splits));
  const sections = [];

  const start = getEventTime(eventMap, "start_tunnel_sensor");
  const mainIn1 = getEventTime(eventMap, "main_in_sensor", 1);
  if (start !== undefined && mainIn1 !== undefined && mainIn1 > start) {
    sections.push({
      start,
      end: mainIn1,
      kind: "run_long",
      label: "Run 1",
      runNumber: 1,
    });
  }

  for (let round = 1; round <= 8; round += 1) {
    const mainIn = getEventTime(eventMap, "main_in_sensor", round);
    const stationIn = getEventTime(eventMap, "station_in_sensor", round);
    if (mainIn !== undefined && stationIn !== undefined && stationIn > mainIn) {
      sections.push({
        start: mainIn,
        end: stationIn,
        kind: "run_in",
        label: `Run In ${round}`,
      });
    }

    if (round < 8) {
      const stationOut = getEventTime(eventMap, "station_out_sensor", round);
      const mainOut = getEventTime(eventMap, "main_out_sensor", round);
      if (stationIn !== undefined && stationOut !== undefined && stationOut > stationIn) {
        sections.push({
          start: stationIn,
          end: stationOut,
          kind: "station",
          label: STATION_NAMES[round] ?? `Station ${round}`,
          round,
        });
      }
      if (stationOut !== undefined && mainOut !== undefined && mainOut > stationOut) {
        sections.push({
          start: stationOut,
          end: mainOut,
          kind: "run_out",
          label: `Run Out ${round}`,
        });
      }
      const nextMainIn = getEventTime(eventMap, "main_in_sensor", round + 1);
      if (mainOut !== undefined && nextMainIn !== undefined && nextMainIn > mainOut) {
        sections.push({
          start: mainOut,
          end: nextMainIn,
          kind: "run_long",
          label: `Run ${round + 1}`,
          runNumber: round + 1,
        });
      }
    } else {
      const finish = getEventTime(eventMap, "finish_line_sensor");
      if (stationIn !== undefined && finish !== undefined && finish > stationIn) {
        sections.push({
          start: stationIn,
          end: finish,
          kind: "finish",
          label: "Finish",
        });
      }
    }
  }

  return sections.sort((a, b) => a.start - b.start);
}

function getSectionState(timeline, t) {
  if (!timeline.length) {
    return { label: "Unknown", since: 0, kind: "unknown", round: null, sectionStart: null };
  }

  if (t < timeline[0].start) {
    return { label: "Pre-Start", since: 0, kind: "prestart", round: null, sectionStart: null };
  }

  let active = timeline[0];
  for (const section of timeline) {
    if (t < section.start) {
      break;
    }
    if (t >= section.start && t < section.end) {
      active = section;
      break;
    }
    active = section;
  }

  const effectiveT = Math.min(t, active.end);
  const since = Math.max(0, effectiveT - active.start);
  if (active.kind === "run_long" && active.runNumber) {
    const span = Math.max(active.end - active.start, 1e-9);
    const frac = Math.min(Math.max((effectiveT - active.start) / span, 0), 0.999999);
    const lap = Math.floor(frac * 3) + 1;
    return {
      label: `Run ${active.runNumber}, Lap ${lap}`,
      since,
      kind: active.kind,
      round: null,
      sectionStart: active.start,
    };
  }
  return {
    label: active.label,
    since,
    kind: active.kind,
    round: active.round ?? null,
    sectionStart: active.start,
  };
}

function formatDuration(seconds) {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${m}:${String(s).padStart(2, "0")}`;
}

function updateBounds(course) {
  let minX = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;

  course.segments.forEach((segment) => {
    segment.points.forEach(([x, y]) => {
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    });
  });

  world.minX = minX;
  world.maxX = maxX;
  world.minY = minY;
  world.maxY = maxY;
}

function toCanvasPoint(x, y) {
  const width = canvas.width - padding * 2;
  const height = canvas.height - padding * 2;
  const xSpan = Math.max(world.maxX - world.minX, 1e-9);
  const ySpan = Math.max(world.maxY - world.minY, 1e-9);
  const nx = (x - world.minX) / xSpan;
  const ny = (y - world.minY) / ySpan;
  return {
    x: padding + nx * width,
    y: canvas.height - (padding + ny * height),
  };
}

function buildStationAnchors(course) {
  const anchors = new Map();
  course.segments.forEach((segment) => {
    const match = /^seg_station_in_to_station_out_r(\d+)$/.exec(segment.id || "");
    if (!match || !segment.points?.length) return;
    const round = Number(match[1]);
    const first = segment.points[0];
    const last = segment.points[segment.points.length - 1];
    anchors.set(round, { start: first, end: last });
  });
  return anchors;
}

function interpolateLinePoint(start, end, fraction) {
  const x = start[0] + (end[0] - start[0]) * fraction;
  const y = start[1] + (end[1] - start[1]) * fraction;
  return [x, y];
}

function buildStationSlotLookup(selectedAthletes, stationEntryByAthleteRound, stationAnchors) {
  const slots = new Map();
  stationAnchors.forEach((stationAnchor, round) => {
    const entries = selectedAthletes
      .map((athlete) => {
        const athleteId = athlete.athlete_id;
        return {
          athleteId,
          entry: stationEntryByAthleteRound.get(`${athleteId}:${round}`),
        };
      })
      .filter((item) => Number.isFinite(item.entry));

    if (!entries.length) return;
    const topPoint =
      stationAnchor.start[1] >= stationAnchor.end[1] ? stationAnchor.start : stationAnchor.end;
    const bottomPoint = topPoint === stationAnchor.start ? stationAnchor.end : stationAnchor.start;
    entries.sort(
      (a, b) => a.entry - b.entry || a.athleteId.localeCompare(b.athleteId),
    );
    const n = entries.length;
    entries.forEach((entry, idx) => {
      const fraction = n === 1 ? 0.5 : 0.1 + (idx / (n - 1)) * 0.8;
      slots.set(`${entry.athleteId}:${round}`, interpolateLinePoint(topPoint, bottomPoint, fraction));
    });
  });
  return slots;
}

function buildStationParkingAssignments(sectionByAthlete, stationSlotLookup) {
  const assignments = new Map();
  sectionByAthlete.forEach((state, athleteId) => {
    if (!state || state.kind !== "station" || state.round == null) return;
    const slot = stationSlotLookup.get(`${athleteId}:${state.round}`);
    if (slot) {
      assignments.set(athleteId, slot);
    }
  });
  return assignments;
}

function drawCourse(course) {
  ctx.save();
  ctx.lineWidth = 2;
  ctx.strokeStyle = "#3a3a3a";
  course.segments.forEach((segment) => {
    if (!segment.points.length) return;
    ctx.beginPath();
    segment.points.forEach(([x, y], idx) => {
      const p = toCanvasPoint(x, y);
      if (idx === 0) {
        ctx.moveTo(p.x, p.y);
      } else {
        ctx.lineTo(p.x, p.y);
      }
    });
    ctx.stroke();
  });
  ctx.restore();
}

function locatePoint(points, t) {
  if (points.length === 0) return [0, 0];
  if (t <= points[0][0]) return [points[0][1], points[0][2]];
  if (t >= points[points.length - 1][0]) {
    const tail = points[points.length - 1];
    return [tail[1], tail[2]];
  }

  let lo = 0;
  let hi = points.length - 1;
  while (lo + 1 < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (points[mid][0] <= t) {
      lo = mid;
    } else {
      hi = mid;
    }
  }

  const left = points[lo];
  const right = points[hi];
  const span = right[0] - left[0];
  if (span <= 0) return [left[1], left[2]];
  const ratio = (t - left[0]) / span;
  const x = left[1] + (right[1] - left[1]) * ratio;
  const y = left[2] + (right[2] - left[2]) * ratio;
  return [x, y];
}

function drawAthletes(athletes, t, stationParking) {
  athletes.forEach((athlete) => {
    const parked = stationParking.get(athlete.athlete_id);
    const [x, y] = parked || locatePoint(athlete.points, t);
    const p = toCanvasPoint(x, y);
    const color = athlete.color || "#8c8c8c";

    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(p.x, p.y, 6, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#e8e8e8";
    ctx.font = "12px sans-serif";
    ctx.fillText(athlete.athlete_id, p.x + 8, p.y - 8);
  });
}

function renderFrame(course, athletes, t, stationParking) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawCourse(course);
  drawAthletes(athletes, t, stationParking);
}

function athleteProgressAtTime(athlete, t) {
  const points = athlete.points;
  if (!points.length) return 0;
  const start = points[0][0];
  const end = points[points.length - 1][0];
  if (end <= start) return 1;
  const clamped = Math.min(Math.max(t, start), end);
  return (clamped - start) / (end - start);
}

function rebuildRankTable(athletes, t, timelinesByAthlete, colorByAthlete) {
  const ranked = athletes
    .map((athlete) => ({
      athlete_id: athlete.athlete_id,
      progress: athleteProgressAtTime(athlete, t),
      section: getSectionState(timelinesByAthlete.get(athlete.athlete_id) ?? [], t),
    }))
    .sort((a, b) => b.progress - a.progress || a.athlete_id.localeCompare(b.athlete_id));

  rankTableBody.innerHTML = "";
  ranked.forEach((item, idx) => {
    const color = colorByAthlete.get(item.athlete_id) ?? "#8c8c8c";
    const progressPct = (item.progress * 100).toFixed(1);
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${idx + 1}</td>
      <td>
        <div class="athlete-cell">
          <span class="chip" style="background:${color}"></span>
          <span>${item.athlete_id}</span>
        </div>
      </td>
      <td>${item.section.label}</td>
      <td>${formatDuration(item.section.since)}</td>
      <td class="progress-cell">
        <div class="progress-track">
          <div class="progress-fill" style="background:${color};width:${progressPct}%"></div>
          <div class="progress-text">${progressPct}%</div>
        </div>
      </td>
    `;
    rankTableBody.appendChild(row);
  });
}

function getSelectedAthleteIds() {
  return new Set(Array.from(athleteSelect.selectedOptions).map((option) => option.value));
}

async function main() {
  try {
    const [course, trajectories] = await Promise.all([
      loadJson(COURSE_URL),
      loadJson(TRAJECTORIES_URL),
    ]);
    const athletes = trajectories.athletes || [];
    const athleteIds = athletes.map((athlete) => athlete.athlete_id);
    const splitsPayload = await loadBestSplits(athleteIds);
    const timelinesByAthlete = new Map();
    const stationEntryByAthleteRound = new Map();
    if (splitsPayload?.athletes) {
      splitsPayload.athletes.forEach((athlete) => {
        const normalizedSplits = normalizeSplitsToElapsed(athlete.splits || []);
        timelinesByAthlete.set(
          athlete.athlete_id,
          buildSectionTimelineForAthlete(normalizedSplits),
        );
        normalizedSplits.forEach((split) => {
          if (split.sensor_type !== "station_in_sensor" || split.round == null) return;
          stationEntryByAthleteRound.set(
            `${athlete.athlete_id}:${split.round}`,
            Number(split.timestamp),
          );
        });
      });
    }
    const tStart = Number(trajectories.meta?.t_start ?? 0);
    const tEnd = Number(trajectories.meta?.t_end ?? 0);
    const duration = Math.max(tEnd - tStart, 0);
    const athletesById = new Map(athletes.map((athlete) => [athlete.athlete_id, athlete]));
    const stationAnchors = buildStationAnchors(course);
    const sortedAthleteIds = [...athleteIds].sort();
    const colorByAthlete = new Map(
      sortedAthleteIds.map((athleteId, idx) => [athleteId, palette[idx % palette.length]]),
    );

    updateBounds(course);
    statusEl.textContent = `${athletes.length} athletes | ${Math.round(duration)}s duration`;
    athleteSelect.innerHTML = "";
    athletes
      .map((athlete) => athlete.athlete_id)
      .sort()
      .forEach((athleteId) => {
        const option = document.createElement("option");
        option.value = athleteId;
        option.textContent = athleteId;
        option.selected = true;
        athleteSelect.appendChild(option);
      });
    let selectedAthleteIds = getSelectedAthleteIds();
    let stationSlotLookup = new Map();

    let playbackSpeed = Number(speedSelect.value) || 8;
    let currentT = tStart;
    let isPlaying = true;
    let lastNow = null;
    let isSeeking = false;

    function updateSeekFromCurrentT() {
      const ratio = duration > 0 ? (currentT - tStart) / duration : 0;
      const sliderValue = Math.round(Math.max(0, Math.min(1, ratio)) * 1000);
      seekSlider.value = String(sliderValue);
    }

    function drawAtCurrentTime() {
      timeEl.textContent = `t=${currentT.toFixed(2)}s`;
      const selectedAthletes = Array.from(selectedAthleteIds)
        .map((athleteId) => athletesById.get(athleteId))
        .filter(Boolean)
        .map((athlete) => ({ ...athlete, color: colorByAthlete.get(athlete.athlete_id) }));
      const sectionByAthlete = new Map(
        selectedAthletes.map((athlete) => [
          athlete.athlete_id,
          getSectionState(timelinesByAthlete.get(athlete.athlete_id) ?? [], currentT),
        ]),
      );
      const stationParking = buildStationParkingAssignments(sectionByAthlete, stationSlotLookup);
      renderFrame(course, selectedAthletes, currentT, stationParking);
      rebuildRankTable(selectedAthletes, currentT, timelinesByAthlete, colorByAthlete);
      if (!isSeeking) {
        updateSeekFromCurrentT();
      }
    }

    function recomputeStationSlots() {
      const selectedAthletes = Array.from(selectedAthleteIds)
        .map((athleteId) => athletesById.get(athleteId))
        .filter(Boolean);
      stationSlotLookup = buildStationSlotLookup(
        selectedAthletes,
        stationEntryByAthleteRound,
        stationAnchors,
      );
    }

    recomputeStationSlots();

    playPauseBtn.addEventListener("click", () => {
      isPlaying = !isPlaying;
      playPauseBtn.textContent = isPlaying ? "Pause" : "Play";
      lastNow = null;
    });

    speedSelect.addEventListener("change", () => {
      const value = Number(speedSelect.value);
      if (!Number.isFinite(value) || value <= 0) return;
      playbackSpeed = value;
    });
    athleteSelect.addEventListener("change", () => {
      const nextSelection = getSelectedAthleteIds();
      // Keep one selected athlete minimum for consistent rendering and ranking.
      if (nextSelection.size === 0) {
        const first = athleteSelect.options[0];
        if (first) {
          first.selected = true;
          selectedAthleteIds = new Set([first.value]);
        }
      } else {
        selectedAthleteIds = nextSelection;
      }
      recomputeStationSlots();
      drawAtCurrentTime();
    });

    seekSlider.addEventListener("pointerdown", () => {
      isSeeking = true;
    });
    seekSlider.addEventListener("pointerup", () => {
      isSeeking = false;
      lastNow = null;
    });
    seekSlider.addEventListener("input", () => {
      const ratio = Number(seekSlider.value) / 1000;
      currentT = tStart + ratio * duration;
      drawAtCurrentTime();
    });

    function tick(now) {
      if (lastNow === null) {
        lastNow = now;
      }

      if (isPlaying && !isSeeking && duration > 0) {
        const deltaSec = (now - lastNow) / 1000;
        currentT += deltaSec * playbackSpeed;
        while (currentT > tEnd) {
          currentT = tStart + (currentT - tEnd);
        }
      }
      lastNow = now;
      drawAtCurrentTime();
      requestAnimationFrame(tick);
    }

    drawAtCurrentTime();
    requestAnimationFrame(tick);
  } catch (err) {
    statusEl.textContent = `Error: ${err instanceof Error ? err.message : String(err)}`;
  }
}

main();

