/**
 * Living Canvas — LeaferJS-powered cognitive flow visualization.
 *
 * Connects to LivingTree's SSE cognition stream to render:
 *   - Intent detection as animated brain nodes
 *   - Tool matching as gear nodes with connections
 *   - Knowledge retrieval as expanding book cards
 *   - Reasoning as recursive tree growth
 *   - Execution as pulsing action nodes
 *
 * Features:
 *   - Pan: drag to move
 *   - Zoom: scroll wheel
 *   - Infinite canvas (LeaferJS 100万图形能力)
 *   - Auto-layout: nodes arrange by phase
 *   - Keyboard: R reset, F fit view
 */

(function () {
  "use strict";

  const { Leafer, Rect, Ellipse, Text, Line, Group, Arrow, PointerEvent, DragEvent } = LeaferUI;

  // ── Canvas Setup ──
  const container = document.getElementById("canvas-container");
  const hint = document.getElementById("hint");
  const statusBar = document.getElementById("status-bar");
  const phaseIndicator = document.getElementById("phase-indicator");
  const currentPhaseEl = document.getElementById("current-phase");
  const phaseDetailEl = document.getElementById("phase-detail");
  const nodeCountEl = document.getElementById("node-count");

  const leafer = new Leafer({
    view: container,
    width: container.clientWidth,
    height: container.clientHeight,
    fill: "transparent",
    cursor: "grab",
  });

  // ── Viewport State ──
  let viewX = container.clientWidth / 2;
  let viewY = container.clientHeight / 2;
  let scale = 1.0;
  let isPanning = false;
  let panStart = { x: 0, y: 0 };
  let viewStart = { x: 0, y: 0 };

  // ── Layout Constants ──
  const NODE_W = 160;
  const NODE_H = 60;
  const LAYER_GAP_X = 220;
  const LAYER_GAP_Y = 100;
  const COLORS = {
    intent: { fill: "#1a2a1a", stroke: "#4a8", text: "#6c8" },
    tools: { fill: "#1a1a2a", stroke: "#68a", text: "#8af" },
    knowledge: { fill: "#2a1a1a", stroke: "#a64", text: "#fa8" },
    reasoning: { fill: "#1a2a2a", stroke: "#4aa", text: "#8ff" },
    execution: { fill: "#2a1a2a", stroke: "#a4a", text: "#f8f" },
    complete: { fill: "#1a2a1a", stroke: "#4a8", text: "#6c8" },
    error: { fill: "#2a1a1a", stroke: "#e05050", text: "#e05050" },
  };

  // ── Track nodes per phase ──
  const phaseNodes = {};
  const allNodes = [];
  let nodeCount = 0;
  let lineCount = 0;
  let lastPhase = null;

  function updateStats() {
    nodeCountEl.textContent = `${nodeCount} 节点 | ${lineCount} 连线 | 活跃`;
  }

  function updatePhase(phase, detail) {
    phaseIndicator.style.display = "block";
    currentPhaseEl.textContent = phase;
    phaseDetailEl.textContent = detail || "";
  }

  // ── Node Creation ──

  function createNode(x, y, text, phase) {
    const color = COLORS[phase] || COLORS.intent;
    const group = new Group({ x, y });

    const rect = new Rect({
      width: NODE_W,
      height: NODE_H,
      cornerRadius: 10,
      fill: color.fill,
      stroke: color.stroke,
      strokeWidth: 1.5,
    });
    group.add(rect);

    const label = new Text({
      text: text.length > 18 ? text.slice(0, 17) + "…" : text,
      fill: color.text,
      fontSize: 13,
      fontWeight: "500",
      textAlign: "center",
      width: NODE_W,
      x: 0,
      y: (NODE_H - 16) / 2,
    });
    group.add(label);

    // Pulse animation
    const glow = new Ellipse({
      x: NODE_W / 2,
      y: NODE_H / 2,
      width: NODE_W + 20,
      height: NODE_H + 20,
      fill: color.stroke,
      opacity: 0.1,
      visible: true,
    });
    group.add(glow);

    leafer.add(group);
    allNodes.push(group);

    if (!phaseNodes[phase]) phaseNodes[phase] = [];
    phaseNodes[phase].push(group);

    nodeCount++;
    hint.style.opacity = "0";

    // Entry animation
    group.scaleX = 0.3;
    group.scaleY = 0.3;
    group.opacity = 0;
    animateIn(group);

    return group;
  }

  function animateIn(group) {
    const start = Date.now();
    const duration = 400;
    function tick() {
      const elapsed = Date.now() - start;
      const t = Math.min(1, elapsed / duration);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      group.scaleX = 0.3 + (1 - 0.3) * eased;
      group.scaleY = 0.3 + (1 - 0.3) * eased;
      group.opacity = Math.min(1, t * 2);
      if (t < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  function createLine(fromNode, toNode, phase) {
    const color = COLORS[phase] || COLORS.intent;
    const fromX = fromNode.x + NODE_W / 2;
    const fromY = fromNode.y + NODE_H;
    const toX = toNode.x + NODE_W / 2;
    const toY = toNode.y;

    const line = new Arrow({
      x: fromX,
      y: fromY,
      points: [0, 0, toX - fromX, toY - fromY],
      stroke: color.stroke,
      strokeWidth: 1.0,
      opacity: 0.4,
      dashPattern: [4, 4],
    });
    leafer.add(line);
    lineCount++;
    return line;
  }

  // ── Layout ──
  function layoutPhases() {
    const phases = ["intent", "tools", "knowledge", "reasoning", "execution"];
    let col = 0;

    phases.forEach((phase) => {
      const nodes = phaseNodes[phase] || [];
      if (nodes.length === 0) return;

      const baseX = viewX + col * LAYER_GAP_X - ((nodes.length - 1) * LAYER_GAP_X) / 6;
      const baseY = viewY - (nodes.length * LAYER_GAP_Y) / 2;

      nodes.forEach((node, i) => {
        node.x = baseX;
        node.y = baseY + i * LAYER_GAP_Y;
      });
      col++;
    });
  }

  // ── SSE Connection ──
  let eventSource = null;

  function connectSSE(message) {
    const url = `/tree/sse/thoughts?q=${encodeURIComponent(message)}`;
    if (eventSource) eventSource.close();

    eventSource = new EventSource(url);

    eventSource.addEventListener("phase", (e) => {
      try {
        const data = JSON.parse(e.data);
        const phase = data.phase || "unknown";
        const label = data.label || phase;
        const detail = data.summary || data.intent || "";

        updatePhase(label, detail);

        if (phase !== lastPhase) {
          lastPhase = phase;
          createNode(viewX + (nodeCount * 30), viewY - 200 + nodeCount * 50, label, phase);
          layoutPhases();
          updateStats();
        }
      } catch (err) {
        // non-critical
      }
    });

    eventSource.addEventListener("token", (e) => {
      try {
        const data = JSON.parse(e.data);
        createNode(viewX + (nodeCount * 30), viewY + nodeCount * 30, data.content.slice(0, 20), "reasoning");
        updateStats();
      } catch (err) {}
    });

    eventSource.addEventListener("complete", () => {
      updatePhase("完成", "认知过程结束");
      updateStats();
      eventSource.close();
    });

    eventSource.addEventListener("error", () => {
      updatePhase("错误", "连接中断");
    });
  }

  // ── Interaction: Pan & Zoom ──
  container.addEventListener("mousedown", (e) => {
    if (e.button === 0) {
      isPanning = true;
      panStart = { x: e.clientX, y: e.clientY };
      viewStart = { x: viewX, y: viewY };
      container.style.cursor = "grabbing";
    }
  });

  window.addEventListener("mousemove", (e) => {
    if (!isPanning) return;
    const dx = e.clientX - panStart.x;
    const dy = e.clientY - panStart.y;
    viewX = viewStart.x + dx / scale;
    viewY = viewStart.y + dy / scale;
    layoutPhases();
  });

  window.addEventListener("mouseup", () => {
    isPanning = false;
    container.style.cursor = "grab";
  });

  container.addEventListener("wheel", (e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    scale = Math.max(0.2, Math.min(5.0, scale * delta));
    statusBar.textContent = `🔍 ${Math.round(scale * 100)}% | 🖱 拖拽移动 | 滚轮缩放`;
  });

  // ── Keyboard ──
  window.addEventListener("keydown", (e) => {
    if (e.key === "r" || e.key === "R") {
      // Reset: clear all nodes
      allNodes.forEach((n) => leafer.remove(n));
      allNodes.length = 0;
      Object.keys(phaseNodes).forEach((k) => delete phaseNodes[k]);
      nodeCount = 0;
      lineCount = 0;
      lastPhase = null;
      viewX = container.clientWidth / 2;
      viewY = container.clientHeight / 2;
      scale = 1.0;
      hint.style.opacity = "1";
      updateStats();
      updatePhase("就绪", "按 R 重置画布");
    }
    if (e.key === "f" || e.key === "F") {
      // Fit view
      viewX = container.clientWidth / 2;
      viewY = container.clientHeight / 2;
      scale = 1.0;
      layoutPhases();
    }
  });

  // ── Expose API ──
  window.LivingCanvas = {
    connect: connectSSE,
    addNode: (text, phase) => {
      const node = createNode(viewX + (nodeCount * 40), viewY + nodeCount * 40, text, phase);
      layoutPhases();
      updateStats();
      return node;
    },
    clear: () => {
      allNodes.forEach((n) => leafer.remove(n));
      allNodes.length = 0;
      Object.keys(phaseNodes).forEach((k) => delete phaseNodes[k]);
      nodeCount = 0;
      lineCount = 0;
      hint.style.opacity = "1";
      updateStats();
    },
    getStats: () => ({ nodes: nodeCount, lines: lineCount, scale }),
  };

  console.log("🌳 Living Canvas initialized (LeaferJS + SSE)");
  console.log("   Pan: drag | Zoom: scroll | Reset: R | Fit: F");
  console.log(`   Canvas: ${container.clientWidth}x${container.clientHeight}`);
})();
