import { forwardRef, useId, type InputHTMLAttributes } from 'react'

type Props = InputHTMLAttributes<HTMLInputElement> & { label: string; description?: string }

export const Checkbox = forwardRef<HTMLInputElement, Props>(function Checkbox(
  { label, description, id, className = '', ...rest },
  ref,
) {
  const auto = useId()
  const fieldId = id ?? auto
  return (
    <label htmlFor={fieldId} className={`flex cursor-pointer items-start gap-3 py-2 ${className}`}>
      <input
        ref={ref}
        id={fieldId}
        type="checkbox"
        className="mt-1 size-5 shrink-0 appearance-none border border-steel-500 bg-steel-900 checked:border-temper-500 checked:bg-temper-500"
        {...rest}
      />
      <span className="flex flex-col">
        <span className="text-base text-steel-100">{label}</span>
        {description && <span className="text-sm text-steel-400">{description}</span>}
      </span>
    </label>
  )
})
