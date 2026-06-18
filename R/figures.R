# figures.R -- R/ggplot2 versions of the three figures (Vital City palette).
# Writes figs_R/fig1_fingerprint.png, fig2_zone_effect.png, fig3_montecarlo.png
suppressMessages({library(data.table); library(ggplot2)})
RED<-"#A8322B"; BLUE<-"#244E78"; GOLD<-"#C7A24A"; GREY<-"#666666"
dir.create("figs_R", showWarnings=FALSE)
th <- theme_minimal(base_size=11) + theme(
  plot.title=element_text(face="bold",size=13,hjust=0),
  plot.subtitle=element_text(size=9,color="#4A4A4A"),
  panel.grid.minor=element_blank(), panel.grid.major.x=element_blank(),
  plot.caption=element_text(size=7.5,color="#999999",hjust=0))

# ---- Figure 1: fingerprint --------------------------------------------------
P <- fread(if (file.exists("data/fingerprint_recip_R.csv")) "data/fingerprint_recip_R.csv" else "data/fingerprint_recip.csv")
P <- P[abs(z)<3 & is.finite(eff_raw) & is.finite(eff_adj)]
P[, `:=`(er=eff_raw, en=eff_adj)]
P[, bin:=cut(z, breaks=seq(min(z),max(z),length.out=11))]
g <- P[, .(z=mean(z), er=mean(er), en=mean(en)), by=bin][!is.na(z)]
d <- rbind(data.table(z=g$z,eff=g$er,Series="Raw year-over-year drop"),
           data.table(z=g$z,eff=g$en,Series="Adjusted for the rebound"))
p1 <- ggplot(d, aes(z,eff,color=Series)) +
  geom_point(size=2.4) +
  geom_smooth(data=rbind(data.table(z=P$z,eff=P$er,Series="Raw year-over-year drop"),
                         data.table(z=P$z,eff=P$en,Series="Adjusted for the rebound")),
              method="lm", se=FALSE, linewidth=1) +
  scale_color_manual(values=c("Raw year-over-year drop"=RED,"Adjusted for the rebound"=BLUE)) +
  labs(title="Precinct efficiency versus the prior-year crime spike",
       subtitle="Efficiency score by prior-year spike (binned means, 77 precincts, 2012-2025)",
       x="Prior-year crime spike (s.d. above precinct trend)",
       y="Efficiency (higher = more efficient)",
       caption="NYPD data via NYC Open Data. R/ggplot2.", color=NULL) +
  th + theme(legend.position="top")
ggsave("figs_R/fig1_fingerprint.png", p1, width=8.6, height=5.2, dpi=130)

# ---- Figure 2: zone-era efficiency gap under three deployment proxies -------
rr <- fread(if (file.exists("data/robustness_recip_R.csv")) "data/robustness_recip_R.csv" else "data/robustness_recip.csv")
didf <- fread(if (file.exists("data/did_R.csv")) "data/did_R.csv" else "data/did_results.csv")
f2 <- rbind(
  data.table(lab="Zone era vs earlier years", coef=rr[input=="arr",zone_coef], lo=rr[input=="arr",ci_lo], hi=rr[input=="arr",ci_hi]),
  data.table(lab="Targeted precincts vs the rest, same years", coef=didf[spec=="real_2023",coef], lo=didf[spec=="real_2023",lo], hi=didf[spec=="real_2023",hi]),
  data.table(lab="An earlier decline (a check)", coef=didf[spec=="placebo_2018",coef], lo=didf[spec=="placebo_2018",lo], hi=didf[spec=="placebo_2018",hi]))
f2[, lab := factor(lab, levels=rev(lab))]
f2[, col := ifelse(lo<=0 & hi>=0, GREY, BLUE)]
p2 <- ggplot(f2, aes(coef, lab, color=I(col))) +
  geom_vline(xintercept=0, color="#1A1A1A", linewidth=0.5) +
  geom_errorbarh(aes(xmin=lo, xmax=hi), height=0, linewidth=3) +
  geom_point(size=3.2) +
  labs(title="The zone-era efficiency gap, before and after removing the citywide decline",
       subtitle="Estimated gap with 95% intervals; comparing targeted precincts with the rest in the same years removes the citywide drop",
       x="Effect on efficiency  (0 = no difference, right = more efficient)", y=NULL,
       caption="Output-oriented VRS, reciprocal (safety) output. R/ggplot2.") + th
ggsave("figs_R/fig2_zone_effect.png", p2, width=9.2, height=3.6, dpi=130)

# ---- Figure 3: Monte Carlo recovery -----------------------------------------
mc <- fread("data/mc_results_R.csv")
m <- rbind(data.table(sigma=mc$sigma,rho=mc$rec_net,Series="Adjusted for the rebound"),
           data.table(sigma=mc$sigma,rho=mc$rec_raw,Series="Raw year-over-year drop"))
p3 <- ggplot(m, aes(sigma,rho,color=Series)) + geom_line(linewidth=1) + geom_point(size=2.4) +
  scale_color_manual(values=c("Raw year-over-year drop"=RED,"Adjusted for the rebound"=BLUE)) +
  ylim(0,0.7) +
  labs(title="Recovery of true efficiency, by year-to-year volatility",
       subtitle="Simulated precincts, deployment sent to last year's hot spots",
       x="Year-to-year crime volatility (transitory s.d.)",
       y="Correlation with true efficiency",
       caption="Monte Carlo, 15 reps/point. R/ggplot2.", color=NULL) +
  th + theme(legend.position="top")
ggsave("figs_R/fig3_montecarlo.png", p3, width=8.6, height=5.0, dpi=130)
cat("wrote figs_R/fig1_fingerprint.png, fig2_zone_effect.png, fig3_montecarlo.png\n")
