import React, {useEffect, useLayoutEffect, useRef, useState} from 'react';

interface IProps {
    initialStyle: React.CSSProperties | undefined;
    compactMode: boolean;
    naturalAspectRatio?: number;
    onResizeStart?: () => void;
    onResizeStop?: () => void;
    children: React.ReactNode;
}

function parsePx(v: string | number | undefined | null): number | null {
    if (typeof v === 'number') return v;
    if (typeof v !== 'string') return null;
    const m = v.match(/^(\d+(?:\.\d+)?)px$/);
    return m ? parseFloat(m[1]) : null;
}

export default function ResizableMediaWrapper({
    initialStyle, compactMode, naturalAspectRatio, onResizeStart, onResizeStop, children
}: IProps) {
    const phaseOneRef = useRef<HTMLDivElement>(null);
    const [width, setWidth] = useState<number | null>(null);
    const minWidthRef = useRef<number>(50);
    const userResized = useRef(false);
    const widthRef = useRef<number | null>(null);
    widthRef.current = width;
    const dragCleanupRef = useRef<(() => void) | null>(null);

    useEffect(() => () => { dragCleanupRef.current?.(); }, []);

    // Phase 1 → Phase 2: browser resolves all CSS rules (%, vh, min/max, etc.) and we
    // capture the resulting pixel width. useLayoutEffect fires before paint → no flicker.
    useLayoutEffect(() => {
        if (compactMode) return;
        const w = phaseOneRef.current?.offsetWidth ?? 0;
        if (w > 0) {
            minWidthRef.current = Math.round(w * 0.5);
            setWidth(w);
        }
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // Once we know the content's natural aspect ratio, apply a maxHeight bounding-box
    // constraint: width = min(measured, maxHeight × aspectRatio).
    // useLayoutEffect keeps this synchronous with the render that produced the new ratio,
    // so the browser never paints the unconstrained intermediate state.
    useLayoutEffect(() => {
        const maxH = parsePx(initialStyle?.maxHeight);
        if (!naturalAspectRatio || maxH === null || userResized.current) return;
        setWidth(prev => {
            if (prev === null) return null;
            const bound = Math.round(maxH * naturalAspectRatio);
            return bound < prev ? bound : prev;
        });
    }, [naturalAspectRatio, initialStyle?.maxHeight]); // eslint-disable-line react-hooks/exhaustive-deps

    const onHandleMouseDown = (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        userResized.current = true;
        const startX = e.clientX;
        const startWidth = widthRef.current ?? 0;
        onResizeStart?.();

        const onMove = (ev: MouseEvent) => {
            setWidth(Math.max(minWidthRef.current, startWidth + ev.clientX - startX));
        };
        const cleanup = () => {
            window.removeEventListener('mousemove', onMove);
            window.removeEventListener('mouseup', onUp);
            dragCleanupRef.current = null;
        };
        const onUp = () => { cleanup(); onResizeStop?.(); };
        dragCleanupRef.current = cleanup;
        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
    };

    if (compactMode) return <>{children}</>;

    // Phase 1: plain div — CSS determines layout, we measure before switching to Phase 2.
    if (width === null) {
        return (
            <div ref={phaseOneRef} style={{...initialStyle, display: 'block'}}>
                {children}
            </div>
        );
    }

    // Phase 2: explicit-width block div + SE drag handle.
    // position: relative is required so the absolute-positioned handle stays anchored here.
    return (
        <div style={{display: 'block', position: 'relative', width, boxSizing: 'border-box'}}>
            <div style={{width: '100%', boxSizing: 'border-box'}}>
                {children}
            </div>
            <div
                aria-hidden="true"
                style={{
                    position: 'absolute',
                    bottom: 0,
                    right: 0,
                    width: 20,
                    height: 20,
                    cursor: 'se-resize',
                    zIndex: 10,
                    // Three diagonal lines pointing SE — classic resize grip
                    backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10'%3E%3Cpath d='M9 3L3 9' stroke='%23888' stroke-width='1.5' stroke-linecap='round'/%3E%3Cpath d='M9 6L6 9' stroke='%23888' stroke-width='1.5' stroke-linecap='round'/%3E%3Ccircle cx='9' cy='9' r='1' fill='%23888'/%3E%3C/svg%3E\")",
                    backgroundRepeat: 'no-repeat',
                    backgroundPosition: 'bottom right',
                    backgroundSize: '10px 10px',
                }}
                onMouseDown={onHandleMouseDown}
            />
        </div>
    );
}
