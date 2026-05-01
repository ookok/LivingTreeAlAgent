<template>
  <div class="terminal-container">
    <div class="terminal-header">
      <div class="header-left">
        <NIcon :component="TerminalIcon" :size="14" />
        <span>终端</span>
        <NButton text size="tiny" @click="newTerminal">
          <NIcon :component="PlusIcon" :size="12" />
        </NButton>
      </div>
      <div class="header-right">
        <NButton text size="tiny" @click="clearTerminal">
          <NIcon :component="TrashIcon" :size="12" />
        </NButton>
        <NButton text size="tiny" @click="toggleFullscreen">
          <NIcon :component="FullscreenIcon" :size="12" />
        </NButton>
        <NButton text size="tiny" @click="$emit('close')">
          <NIcon :component="XIcon" :size="12" />
        </NButton>
      </div>
    </div>
    
    <div ref="terminalWrapper" class="terminal-wrapper">
      <div ref="terminalElement" class="terminal"></div>
    </div>
    
    <div class="terminal-input-area">
      <span class="prompt">{{ currentDir }}</span>
      <input
        ref="inputRef"
        v-model="currentCommand"
        class="command-input"
        @keydown="handleKeyDown"
        placeholder="输入命令..."
        spellcheck="false"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { NButton, NIcon } from 'naive-ui'
import { Terminal, Plus, Trash2, Maximize2, X } from '@vicons/ionicons5'
import { Terminal as XTerminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'

const TerminalIcon = { render: () => h(Terminal) }
const PlusIcon = { render: () => h(Plus) }
const TrashIcon = { render: () => h(Trash2) }
const FullscreenIcon = { render: () => h(Maximize2) }
const XIcon = { render: () => h(X) }

defineEmits(['close'])

const terminalElement = ref(null)
const terminalWrapper = ref(null)
const inputRef = ref(null)
const currentCommand = ref('')
const currentDir = ref('$')

let terminal = null
let fitAddon = null
const commandHistory = []
let historyIndex = -1

function initTerminal() {
  if (!terminalElement.value) return
  
  terminal = new XTerminal({
    cursorBlink: true,
    cursorStyle: 'block',
    fontSize: 13,
    fontFamily: "'JetBrains Mono', 'Consolas', monospace",
    lineHeight: 1.4,
    theme: {
      background: '#0f172a',
      foreground: '#f8fafc',
      cursor: '#f8fafc',
      cursorAccent: '#0f172a',
      selection: '#3b82f6',
      black: '#1e293b',
      red: '#ef4444',
      green: '#22c55e',
      yellow: '#f59e0b',
      blue: '#3b82f6',
      magenta: '#a855f7',
      cyan: '#06b6d4',
      white: '#f8fafc',
      brightBlack: '#475569',
      brightRed: '#f87171',
      brightGreen: '#4ade80',
      brightYellow: '#fbbf24',
      brightBlue: '#60a5fa',
      brightMagenta: '#c084fc',
      brightCyan: '#22d3ee',
      brightWhite: '#ffffff'
    }
  })
  
  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  
  terminal.open(terminalElement.value)
  fitAddon.fit()
  
  terminal.write('Welcome to LivingTree AI Terminal\n')
  terminal.write('Type "help" for available commands\n\n')
  terminal.write('$ ')
  
  terminal.onKey((e) => {
    if (e.domEvent.key === 'Enter') {
      executeCommand(currentCommand.value)
    }
  })
}

function executeCommand(command) {
  if (!command.trim()) {
    terminal.write('\n$ ')
    return
  }
  
  commandHistory.push(command)
  historyIndex = commandHistory.length
  
  terminal.write(`\n${command}\n`)
  
  const output = executeShellCommand(command)
  terminal.write(`${output}\n`)
  terminal.write('$ ')
  
  currentCommand.value = ''
  nextTick(() => {
    inputRef.value?.focus()
  })
}

function executeShellCommand(command) {
  const cmd = command.trim().toLowerCase()
  
  if (cmd === 'help') {
    return `Available commands:
  help          - Show this help message
  ls            - List directory contents
  pwd           - Print current directory
  cd [dir]      - Change directory
  clear         - Clear terminal
  echo [text]   - Print text
  date          - Show current date
  whoami        - Show current user
  python        - Run Python script
  node          - Run Node.js script
  git [cmd]     - Git commands`
  }
  
  if (cmd === 'ls') {
    const fs = require('fs')
    const path = require('path')
    try {
      const files = fs.readdirSync('.')
      return files.join('\n')
    } catch (e) {
      return `Error: ${e.message}`
    }
  }
  
  if (cmd === 'pwd') {
    return require('process').cwd()
  }
  
  if (cmd.startsWith('cd ')) {
    const dir = cmd.substring(3).trim()
    try {
      process.chdir(dir)
      currentDir.value = `$ ${process.cwd()}`
      return ''
    } catch (e) {
      return `Error: ${e.message}`
    }
  }
  
  if (cmd === 'clear') {
    terminal.clear()
    terminal.write('$ ')
    return ''
  }
  
  if (cmd.startsWith('echo ')) {
    return cmd.substring(5)
  }
  
  if (cmd === 'date') {
    return new Date().toString()
  }
  
  if (cmd === 'whoami') {
    return require('os').userInfo().username
  }
  
  return `Command not found: ${command}. Type "help" for available commands.`
}

function handleKeyDown(e) {
  if (e.key === 'Enter') {
    e.preventDefault()
    executeCommand(currentCommand.value)
  }
  
  if (e.key === 'ArrowUp') {
    e.preventDefault()
    if (historyIndex > 0) {
      historyIndex--
      currentCommand.value = commandHistory[historyIndex]
    }
  }
  
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    if (historyIndex < commandHistory.length - 1) {
      historyIndex++
      currentCommand.value = commandHistory[historyIndex]
    } else {
      historyIndex = commandHistory.length
      currentCommand.value = ''
    }
  }
  
  if (e.key === 'Tab') {
    e.preventDefault()
    autocomplete()
  }
}

function autocomplete() {
  const fs = require('fs')
  const path = require('path')
  
  const parts = currentCommand.value.split(' ')
  const lastPart = parts[parts.length - 1]
  
  if (lastPart.startsWith('/')) {
    const dir = path.dirname(lastPart)
    const prefix = path.basename(lastPart)
    
    try {
      const files = fs.readdirSync(dir || '.')
      const matches = files.filter(f => f.startsWith(prefix))
      if (matches.length === 1) {
        parts[parts.length - 1] = matches[0]
        currentCommand.value = parts.join(' ')
      }
    } catch (e) {
      console.error('Autocomplete error:', e)
    }
  }
}

function clearTerminal() {
  terminal?.clear()
  terminal?.write('$ ')
}

function newTerminal() {
  terminal?.clear()
  terminal?.write('Welcome to LivingTree AI Terminal\n')
  terminal?.write('$ ')
  currentCommand.value = ''
}

function toggleFullscreen() {
  console.log('Toggle fullscreen')
}

function handleResize() {
  fitAddon?.fit()
}

onMounted(() => {
  initTerminal()
  window.addEventListener('resize', handleResize)
  nextTick(() => {
    inputRef.value?.focus()
  })
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  terminal?.dispose()
})
</script>

<style scoped>
.terminal-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-dark);
  border-radius: 8px;
  overflow: hidden;
}

.terminal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.header-left, .header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-left span {
  font-size: 12px;
  color: var(--text-secondary);
}

.terminal-wrapper {
  flex: 1;
  overflow: hidden;
}

.terminal {
  width: 100%;
  height: 100%;
}

.terminal-input-area {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
}

.prompt {
  color: var(--success-color);
  font-family: monospace;
  font-size: 13px;
}

.command-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-family: monospace;
  font-size: 13px;
}

.command-input::placeholder {
  color: var(--text-secondary);
}
</style>