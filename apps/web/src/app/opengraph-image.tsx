import { ImageResponse } from 'next/og';

export const alt = 'Zylora AI website builder and professional Template platform';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

export default function OpenGraphImage() {
  return new ImageResponse(
    <div
      style={{
        display: 'flex',
        width: '100%',
        height: '100%',
        flexDirection: 'column',
        justifyContent: 'space-between',
        background: '#070808',
        color: '#f5f6f2',
        padding: '72px',
        fontFamily: 'Arial, sans-serif',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '18px',
          fontSize: 34,
          fontWeight: 800,
        }}
      >
        <div style={{ display: 'flex', color: '#d9ff6b', fontSize: 48 }}>Z</div>
        Zylora
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', maxWidth: 950 }}>
        <div style={{ color: '#d9ff6b', fontSize: 22, fontWeight: 800, letterSpacing: '0.12em' }}>
          AI WEBSITE BUILDER + PROFESSIONAL TEMPLATES
        </div>
        <div
          style={{
            marginTop: 24,
            fontSize: 84,
            fontWeight: 800,
            lineHeight: 0.98,
            letterSpacing: '-0.055em',
          }}
        >
          Build a professional website your way.
        </div>
      </div>
      <div style={{ display: 'flex', color: '#a7aaa3', fontSize: 25 }}>
        Create. Edit. Publish. Capture Leads.
      </div>
    </div>,
    size,
  );
}
