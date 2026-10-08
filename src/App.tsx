import React from 'react';

export default function App() {
  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#000000',
      color: '#FFFFFF',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
      boxSizing: 'border-box',
      textAlign: 'center'
    }}>
      <div style={{
        display: 'inline-block',
        padding: '6px 16px',
        border: '1px solid #27272A',
        borderRadius: '9999px',
        fontSize: '12px',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        color: '#A1A1AA',
        marginBottom: '24px'
      }}>
        NASA Space Apps Challenge 2026 · Bangladesh
      </div>
      <h1 style={{ fontSize: '38px', fontWeight: 700, margin: '0 0 16px 0', letterSpacing: '-0.02em' }}>
        Team ChhayaNautical
      </h1>
      <p style={{ color: '#A1A1AA', fontSize: '16px', maxWidth: '540px', lineHeight: 1.6, margin: '0 0 32px 0' }}>
        Official team website assembling from Figma designs (Habitat, Expeditions, Crew & Share Cards Widget).
      </p>
      <div style={{ fontSize: '12px', color: '#FF4D00', fontFamily: 'monospace' }}>
        ● WORKFLOW: AUTO_DEPLOY_ENABLED (Target: chhayanautical.web.app)
      </div>
    </div>
  );
}
