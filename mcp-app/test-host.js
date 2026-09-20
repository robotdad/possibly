import { AppBridge, PostMessageTransport } from '@modelcontextprotocol/ext-apps/app-bridge';
window.mountPossibly = async (html, result, options = {}) => {
  const frame = document.createElement('iframe');
  frame.id='app'; frame.sandbox='allow-scripts allow-downloads';
  frame.style=`width:${options.width || '100%'};height:${options.height || '900px'};border:0`;
  document.body.replaceChildren(frame);
  const bridge = new AppBridge(null,{name:'Independent fixture host',version:'1.0.0'},{serverTools:{},updateModelContext:{}},{hostContext:{theme:options.theme || 'dark',displayMode:'inline'}});
  bridge.oncalltool = args => window.hostCall(args);
  bridge.onupdatemodelcontext = async args => {window.savedContext=args; return {};};
  bridge.oninitialized = async () => {
    if (!result) return;
    await bridge.sendToolInput({arguments:{exploration_id:result.structuredContent.exploration_id}});
    await bridge.sendToolResult(result);
  };
  await bridge.connect(new PostMessageTransport(frame.contentWindow,frame.contentWindow));
  frame.srcdoc=html;
  window.possiblyBridge=bridge;
  window.sendPossiblyHostContext = context => bridge.notification({
    method:'ui/notifications/host-context-changed', params:context,
  });
};
