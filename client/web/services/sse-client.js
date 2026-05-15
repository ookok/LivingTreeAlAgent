/* SSE Client — Server-Sent Events with exponential backoff reconnect
 * 
 * Replaces polling setInterval with persistent push connection.
 * Auto-reconnects on connection loss with exponential backoff (1s→2s→4s→...→30s max).
 * 
 * Usage:
 *   LT.sse.connect('/api/stream/vitals', {
 *     vitals: function(data) { ... },
 *     task_update: function(data) { ... }
 *   });
 */

(function() {
  'use strict';
  window.LT = window.LT || {};

  const SSEClient = {
    _connections: {},
    _retryDelays: {},

    /** Connect to an SSE endpoint with typed event handlers */
    connect(url, handlers) {
      if (this._connections[url]) {
        this._connections[url].close();
      }
      this._retryDelays[url] = 1000;
      this._connect(url, handlers);
    },

    _connect(url, handlers) {
      const es = new EventSource(url);
      this._connections[url] = es;

      es.onopen = () => {
        this._retryDelays[url] = 1000;
      };

      // Typed event handlers
      for (const [eventType, handler] of Object.entries(handlers)) {
        es.addEventListener(eventType, (e) => {
          try {
            const data = JSON.parse(e.data);
            handler(data);
          } catch(err) {
            // Non-JSON events: pass raw text
            handler(e.data);
          }
        });
      }

      // Generic message fallback
      es.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          const type = data.type || data.event;
          if (type && handlers[type]) {
            handlers[type](data);
          }
        } catch(err) {}
      };

      // Auto-reconnect with exponential backoff
      es.onerror = () => {
        es.close();
        const delay = this._retryDelays[url];
        this._retryDelays[url] = Math.min(delay * 2, 30000);
        setTimeout(() => this._connect(url, handlers), delay);
      };
    },

    /** Disconnect from an endpoint */
    disconnect(url) {
      const es = this._connections[url];
      if (es) {
        es.close();
        delete this._connections[url];
        delete this._retryDelays[url];
      }
    },

    /** Disconnect all */
    disconnectAll() {
      for (const url of Object.keys(this._connections)) {
        this.disconnect(url);
      }
    }
  };

  LT.sse = SSEClient;

  // Cleanup on page unload
  window.addEventListener('beforeunload', () => SSEClient.disconnectAll());
})();
