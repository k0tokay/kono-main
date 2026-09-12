export function RightClickMenu({ items, x = 0, y = 0, isMenuVisible = false }) {
    if (!isMenuVisible) return null;

    return (
        <ul className="rightClickMenu"
            style={{
                top: `${y}px`,
                left: `${x}px`,
            }}
        >
            {items.map((item, i) => (
                <li
                    key={i}
                    onClick={item.onClick}
                    className="RCMenuItem"
                >
                    {item.title}
                </li>
            ))}
        </ul>
    );
};
