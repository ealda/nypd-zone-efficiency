# maps.R -- R twin of 09_maps.py. Precinct choropleths, 2022 vs 2025:
# summer shootings per square mile and reciprocal (safety) efficiency,
# output-oriented VRS. Parses the GeoJSON with jsonlite, draws with ggplot2,
# and reconciles the per-precinct values against the Python data/maps_values.csv.
suppressMessages({library(data.table); library(lpSolve); library(jsonlite); library(ggplot2)})
dir.create("figs_R", showWarnings=FALSE)
BEFORE <- 2022; AFTER <- 2025; SQFT_PER_SQMI <- 27878400

gj <- fromJSON("data/precincts.geojson", simplifyVector=FALSE)
poly <- list(); area <- c()
for (ft in gj$features){
  pc <- as.integer(ft$properties$precinct); area[as.character(pc)] <- as.numeric(ft$properties$shape_area)/SQFT_PER_SQMI
  polys <- if (ft$geometry$type=="MultiPolygon") ft$geometry$coordinates else list(ft$geometry$coordinates)
  for (pi in seq_along(polys)){
    ring <- polys[[pi]][[1]]
    m <- do.call(rbind, lapply(ring, function(z) c(z[[1]], z[[2]])))
    poly[[length(poly)+1]] <- data.table(pct=pc, piece=paste0(pc,"_",pi), lon=m[,1], lat=m[,2])
  }
}
POLY <- rbindlist(poly)

P <- fread(if (file.exists("data/panel_R.csv")) "data/panel_R.csv" else "data/panel.csv")
sd_by <- function(y){ s <- P[yr==y]; setNames(s$shoot/area[as.character(s$pct)], s$pct) }

dea_out <- function(x, Y){
  x <- x/mean(x); Y <- sweep(Y,2,colMeans(Y),"/"); n <- length(x); sO <- ncol(Y); eff <- rep(NA_real_,n)
  for (o in 1:n){ con <- rbind(c(0,x)); dir <- "<="; rhs <- x[o]
    for (q in 1:sO){ con <- rbind(con, c(Y[o,q], -Y[,q])); dir <- c(dir,"<="); rhs <- c(rhs,0) }
    con <- rbind(con, c(0,rep(1,n))); dir <- c(dir,"="); rhs <- c(rhs,1)
    s <- lp("max", c(1,rep(0,n)), con, dir, rhs); if (s$status==0 && s$objval>=1e-9) eff[o] <- 1/s$objval }
  eff
}
eff_by <- function(y){
  d <- P[yr==y][is.finite(arr)&is.finite(shoot_pred)&is.finite(viol_pred)]
  Y <- cbind((d$shoot_pred+1)/(d$shoot+1), (d$viol_pred+1)/(d$viol+1))
  setNames(dea_out(pmax(d$arr,1), Y), d$pct)
}
sdb <- sd_by(BEFORE); sda <- sd_by(AFTER); efb <- eff_by(BEFORE); efa <- eff_by(AFTER)
s22 <- setNames(P[yr==BEFORE]$shoot, P[yr==BEFORE]$pct)
targeted <- as.integer(names(s22)[s22 >= quantile(s22, 2/3)])

# reconcile against Python maps_values.csv
if (file.exists("data/maps_values.csv")){
  mv <- fread("data/maps_values.csv")
  cmp <- data.table(pct=mv$pct,
                    d_sdb=abs(mv$sd_before-sdb[as.character(mv$pct)]),
                    d_efa=abs(mv$eff_after-efa[as.character(mv$pct)]))
  cat("maps reconcile vs Python | max |sd_before diff|:", round(max(cmp$d_sdb,na.rm=TRUE),4),
      "| max |eff_after diff|:", round(max(cmp$d_efa,na.rm=TRUE),4), "\n")
}

mk <- function(valmap, title, fill_lab, diverging=FALSE){
  D <- copy(POLY); D[, val := valmap[as.character(pct)]]
  g <- ggplot(D, aes(lon, lat, group=piece, fill=val)) +
    geom_polygon(color="white", linewidth=0.1) +
    geom_polygon(data=D[pct %in% targeted], color="#1A1A1A", linewidth=0.4, fill=NA) +
    coord_quickmap() + theme_void(base_size=10) +
    labs(title=title, fill=fill_lab) + theme(plot.title=element_text(face="bold",size=11))
  if (diverging) g <- g + scale_fill_gradient2(midpoint=median(c(efb,efa),na.rm=TRUE), low="#A8322B", mid="#EEEEEE", high="#244E78")
  else g <- g + scale_fill_gradient(low="#FFF5F0", high="#A8322B")
  g
}
ggsave("figs_R/fig4_shoot_2022.png", mk(sdb,"Shootings per sq mi, 2022","per sq mi"), width=5, height=5.5, dpi=120)
ggsave("figs_R/fig4_shoot_2025.png", mk(sda,"Shootings per sq mi, 2025","per sq mi"), width=5, height=5.5, dpi=120)
ggsave("figs_R/fig4_eff_2022.png",   mk(efb,"Efficiency, 2022","efficiency",TRUE), width=5, height=5.5, dpi=120)
ggsave("figs_R/fig4_eff_2025.png",   mk(efa,"Efficiency, 2025","efficiency",TRUE), width=5, height=5.5, dpi=120)
cat("wrote figs_R/fig4_*.png\n")
