<template>
  <a-config-provider :theme="themeConfig">
    <a-layout class="app-layout">
      <a-layout-sider
        v-model:collapsed="collapsed"
        :trigger="null"
        :width="260"
        :collapsed-width="72"
        class="sidebar"
      >
        <!-- Logo -->
        <div class="sidebar-header">
          <div class="logo-wrapper">
            <div class="logo-icon">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="3" y="3" width="7" height="7" rx="2" fill="currentColor" opacity="0.9"/>
                <rect x="14" y="3" width="7" height="7" rx="2" fill="currentColor" opacity="0.6"/>
                <rect x="3" y="14" width="7" height="7" rx="2" fill="currentColor" opacity="0.6"/>
                <rect x="14" y="14" width="7" height="7" rx="2" fill="currentColor" opacity="0.3"/>
              </svg>
            </div>
            <transition name="fade-text">
              <div v-if="!collapsed" class="logo-text">
                <span class="brand">UI Config</span>
                <span class="tagline">智能配置系统</span>
              </div>
            </transition>
          </div>
        </div>
        
        <!-- Navigation -->
        <nav class="sidebar-nav dark-scrollbar">
          <div class="nav-section">
            <span v-if="!collapsed" class="nav-label">主要功能</span>
          </div>
          
          <a-menu
            v-model:selectedKeys="selectedKeys"
            mode="inline"
            :inline-collapsed="collapsed"
          >
            <a-menu-item key="/intent">
              <template #icon>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
                  <circle cx="12" cy="12" r="10"/>
                  <path d="M12 16v-4M12 8h.01"/>
                </svg>
              </template>
              <router-link to="/intent">意图配置</router-link>
            </a-menu-item>
            
            <a-menu-item key="/">
              <template #icon>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
                  <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
              </template>
              <router-link to="/">页面配置</router-link>
            </a-menu-item>
            
            <a-menu-item key="/system-prompt">
              <template #icon>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
                  <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                </svg>
              </template>
              <router-link to="/system-prompt">提示词配置</router-link>
            </a-menu-item>
            
            <a-menu-item key="/mcp">
              <template #icon>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
                  <path d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"/>
                </svg>
              </template>
              <router-link to="/mcp">MCP 服务器</router-link>
            </a-menu-item>
            
            <a-menu-item key="/mcp-host">
              <template #icon>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
                  <path d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/>
                </svg>
              </template>
              <router-link to="/mcp-host">MCP Host</router-link>
            </a-menu-item>
            
            <a-menu-item key="/sampling">
              <template #icon>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
                  <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                </svg>
              </template>
              <router-link to="/sampling">Sampling</router-link>
            </a-menu-item>
          </a-menu>
        </nav>
        
        <!-- Footer -->
        <div class="sidebar-footer">
          <div class="footer-content">
            <button class="collapse-btn" @click="collapsed = !collapsed">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ rotated: collapsed }">
                <path d="M11 19l-7-7 7-7m8 14l-7-7 7-7"/>
              </svg>
            </button>
            <transition name="fade-text">
              <div v-if="!collapsed" class="version-info">
                <span class="version">v1.0.0</span>
                <span class="status">
                  <span class="status-dot"></span>
                  已连接
                </span>
              </div>
            </transition>
          </div>
        </div>
      </a-layout-sider>
      
      <a-layout class="main-layout">
        <a-layout-content class="main-content">
          <router-view v-slot="{ Component }">
            <transition name="page-fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </a-layout-content>
      </a-layout>
    </a-layout>
  </a-config-provider>
</template>

<script setup>
import { ref, watch, reactive } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const selectedKeys = ref(['/']);
const collapsed = ref(false);

const themeConfig = reactive({
  token: {
    colorPrimary: '#6366f1',
    borderRadius: 8,
    fontFamily: "'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  },
});

watch(
  () => route.path,
  (path) => {
    // 处理动态路由
    if (path.startsWith('/page/')) {
      selectedKeys.value = ['/'];
    } else if (path === '/intent') {
      selectedKeys.value = ['/intent'];
    } else {
      selectedKeys.value = [path];
    }
  },
  { immediate: true }
);
</script>

<style lang="scss">
.app-layout {
  min-height: 100vh;
}

.sidebar {
  position: fixed !important;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 100;
  display: flex;
  flex-direction: column;
  
  .ant-layout-sider-children {
    display: flex;
    flex-direction: column;
    height: 100%;
  }
}

.sidebar-header {
  padding: 24px 20px 20px;
  border-bottom: 1px solid var(--sidebar-border);
  
  .logo-wrapper {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  
  .logo-icon {
    width: 40px;
    height: 40px;
    background: linear-gradient(135deg, var(--primary) 0%, #818cf8 100%);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    
    svg {
      width: 22px;
      height: 22px;
      color: white;
    }
  }
  
  .logo-text {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    
    .brand {
      font-size: 17px;
      font-weight: 700;
      color: white;
      letter-spacing: -0.02em;
      line-height: 1.2;
    }
    
    .tagline {
      font-size: 11px;
      color: var(--sidebar-text-muted);
      letter-spacing: 0.01em;
      margin-top: 2px;
    }
  }
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
  
  .nav-section {
    padding: 0 24px;
    margin-bottom: 8px;
  }
  
  .nav-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--sidebar-text-muted);
  }
  
  .nav-icon {
    width: 20px;
    height: 20px;
  }
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--sidebar-border);
  
  .footer-content {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  
  .collapse-btn {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    border: none;
    background: var(--sidebar-hover);
    color: var(--sidebar-text);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
    flex-shrink: 0;
    
    &:hover {
      background: rgba(255, 255, 255, 0.12);
    }
    
    svg {
      width: 16px;
      height: 16px;
      transition: transform 0.3s;
      
      &.rotated {
        transform: rotate(180deg);
      }
    }
  }
  
  .version-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
    overflow: hidden;
    
    .version {
      font-size: 12px;
      color: var(--sidebar-text-muted);
      font-weight: 500;
    }
    
    .status {
      font-size: 11px;
      color: #10b981;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    
    .status-dot {
      width: 6px;
      height: 6px;
      background: #10b981;
      border-radius: 50%;
      animation: pulse-dot 2s infinite;
    }
  }
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.main-layout {
  margin-left: 260px;
  background: var(--bg-body);
  min-height: 100vh;
  transition: margin-left 0.2s;
  
  .ant-layout-sider-collapsed + & {
    margin-left: 72px;
  }
}

// 处理侧边栏折叠
.ant-layout-sider-collapsed {
  & + .main-layout {
    margin-left: 72px;
  }
}

.main-content {
  min-height: 100vh;
  overflow-y: auto;
}

// 页面切换动画
.page-fade-enter-active {
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.page-fade-leave-active {
  transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

// 文字淡入淡出
.fade-text-enter-active,
.fade-text-leave-active {
  transition: all 0.2s ease;
}

.fade-text-enter-from,
.fade-text-leave-to {
  opacity: 0;
  transform: translateX(-8px);
}
</style>
