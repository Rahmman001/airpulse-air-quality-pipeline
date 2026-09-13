import React from 'react';

interface EtoileStarProps {
  size?: number;
  className?: string;
  fill?: string;
}

export const EtoileStar: React.FC<EtoileStarProps> = ({
  size = 14,
  className = '',
  fill = 'currentColor',
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={fill}
      className={`inline-block shrink-0 ${className}`}
      aria-hidden="true"
    >
      <path d="M12 0C12 6.627 6.627 12 0 12c6.627 0 12 5.373 12 12 0-6.627 5.373-12 12-12-6.627 0-12-5.373-12-12z" />
    </svg>
  );
};
