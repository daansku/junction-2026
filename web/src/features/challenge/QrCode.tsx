import { useEffect, useState } from 'react'
import QRCode from 'qrcode'

/** Dark modules on white with a quiet zone: the one layout every phone camera reads. */
export function QrCode({ text, size = 128 }: { text: string; size?: number }) {
  const [svg, setSvg] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    QRCode.toString(text, { type: 'svg', margin: 2, errorCorrectionLevel: 'M', color: { dark: '#000000', light: '#ffffff' } })
      .then((s) => alive && setSvg(s))
      .catch(() => alive && setSvg(null))
    return () => {
      alive = false
    }
  }, [text])
  if (!svg) return <div className="ch-qr-box" style={{ width: size, height: size }} aria-hidden />
  return (
    <div
      className="ch-qr-box"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`QR code for ${text}`}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
