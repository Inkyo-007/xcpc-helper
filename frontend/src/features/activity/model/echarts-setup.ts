/** ECharts 按需注册：只打包日历热力图与柱状图所需模块。 */

import { BarChart, HeatmapChart } from 'echarts/charts'
import { CalendarComponent, GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'

echarts.use([BarChart, HeatmapChart, CalendarComponent, GridComponent, TooltipComponent, SVGRenderer])

export { echarts }
export type { EChartsCoreOption } from 'echarts/core'
