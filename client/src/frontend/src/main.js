/**
 * Vue.js 主入口文件
 */

import { createApp } from 'vue';
import App from './App.vue';

// 创建Vue应用
const app = createApp(App);

// 挂载到DOM
app.mount('#app');

// 导出应用实例（用于扩展）
export { app };