<template>
  <div class="app">
    <nav class="sidebar">
      <div class="logo">
        <div class="logo-icon">⚙️</div>
        <h1>UI Config</h1>
      </div>
      
      <ul class="nav-menu">
        <li>
          <router-link to="/" class="nav-item" active-class="active">
            <span class="icon">📄</span>
            <span class="text">页面配置</span>
          </router-link>
        </li>
        <li>
          <router-link to="/system-prompt" class="nav-item" active-class="active">
            <span class="icon">💬</span>
            <span class="text">提示词配置</span>
          </router-link>
        </li>
        <li>
          <router-link to="/mcp" class="nav-item" active-class="active">
            <span class="icon">🔌</span>
            <span class="text">MCP 服务器</span>
          </router-link>
        </li>
      </ul>
      
      <div class="nav-footer">
        <div class="version">v1.0.0 Demo</div>
      </div>
    </nav>
    
    <main class="main-content">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
// 主应用组件
</script>

<style lang="scss">
.app {
  display: flex;
  min-height: 100vh;
  background: var(--bg-primary);
}

.sidebar {
  width: 240px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 100;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px 20px;
  border-bottom: 1px solid var(--border-color);
  
  .logo-icon {
    font-size: 28px;
  }
  
  h1 {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }
}

.nav-menu {
  list-style: none;
  padding: 16px 12px;
  margin: 0;
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  color: var(--text-secondary);
  text-decoration: none;
  transition: all 0.2s ease;
  margin-bottom: 4px;
  
  .icon {
    font-size: 18px;
  }
  
  .text {
    font-size: 14px;
    font-weight: 500;
  }
  
  &:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }
  
  &.active {
    background: var(--primary-light);
    color: var(--primary);
    
    .icon {
      transform: scale(1.1);
    }
  }
}

.nav-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
  
  .version {
    font-size: 12px;
    color: var(--text-muted);
  }
}

.main-content {
  flex: 1;
  margin-left: 240px;
  min-height: 100vh;
}

// 页面切换动画
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

