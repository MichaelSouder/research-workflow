import * as React from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { DayPicker, getDefaultClassNames } from 'react-day-picker'

import { cn } from '@/lib/utils'
import { buttonVariants } from '@/components/ui/button'

import 'react-day-picker/style.css'

/** RDP merges `{...defaults, ...classNames}`; values must keep `rdp-*` tokens or layout/CSS breaks. */
const defaultClassNames = getDefaultClassNames()

function Calendar({ className, classNames, showOutsideDays = true, ...props }) {
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      className={cn('p-3', className)}
      classNames={{
        ...defaultClassNames,
        root: cn(defaultClassNames.root, 'w-fit'),
        months: cn(defaultClassNames.months, 'flex flex-col gap-4'),
        month: cn(defaultClassNames.month, 'space-y-4'),
        month_caption: cn(defaultClassNames.month_caption, 'flex items-center justify-center pt-1'),
        caption_label: cn(defaultClassNames.caption_label, 'text-sm font-medium'),
        button_previous: cn(
          defaultClassNames.button_previous,
          buttonVariants({ variant: 'outline' }),
          'size-7 bg-transparent p-0 opacity-80 hover:opacity-100'
        ),
        button_next: cn(
          defaultClassNames.button_next,
          buttonVariants({ variant: 'outline' }),
          'size-7 bg-transparent p-0 opacity-80 hover:opacity-100'
        ),
        month_grid: cn(defaultClassNames.month_grid, 'w-full border-collapse'),
        weekdays: cn(defaultClassNames.weekdays, 'flex'),
        weekday: cn(defaultClassNames.weekday, 'text-muted-foreground w-8 text-[0.7rem] font-normal'),
        week: cn(defaultClassNames.week, 'mt-2 flex w-full'),
        day: cn(defaultClassNames.day, 'p-0'),
        day_button: cn(
          defaultClassNames.day_button,
          buttonVariants({ variant: 'ghost' }),
          'size-8 p-0 font-normal aria-selected:opacity-100'
        ),
        selected: cn(
          defaultClassNames.selected,
          'bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground focus:bg-primary focus:text-primary-foreground'
        ),
        today: cn(defaultClassNames.today, 'bg-accent text-accent-foreground'),
        outside: cn(defaultClassNames.outside, 'text-muted-foreground opacity-50'),
        disabled: cn(defaultClassNames.disabled, 'text-muted-foreground opacity-50'),
        hidden: cn(defaultClassNames.hidden, 'invisible'),
        ...classNames,
      }}
      components={{
        Chevron: ({ orientation, className: iconClass, ...rest }) =>
          orientation === 'left' ? (
            <ChevronLeft className={cn('size-4', iconClass)} {...rest} />
          ) : (
            <ChevronRight className={cn('size-4', iconClass)} {...rest} />
          ),
      }}
      {...props}
    />
  )
}
Calendar.displayName = 'Calendar'

export { Calendar }
